import os
from pathlib import Path
import re
import subprocess
import tempfile
import textwrap
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
COMMIT = "a" * 40
BRANCH = "releases/v7.0.2"
CHECK_NAME = "1ES private-cluster release gate"
ENVIRONMENT = {
    "CANDIDATE_REPOSITORY": "Azure/k8s-deploy",
    "CANDIDATE_BRANCH": BRANCH,
    "CANDIDATE_COMMIT": COMMIT,
    "CANDIDATE_VERSION": "v7.0.2",
    "REQUIRED_CHECK_NAME": CHECK_NAME,
    "REQUIRED_CHECK_APP_ID": "123",
    "CHECK_TIMEOUT_MINUTES": "90",
}


def load_gate():
    text = (WORKFLOWS / "check_release_candidate.yaml").read_text()
    source = text.split("python3 - <<'PY'\n", 1)[1]
    source = re.split(r"\n +PY\s*$", source)[0]
    module = types.ModuleType("release_gate")
    exec(compile(textwrap.dedent(source), "release_gate", "exec"), module.__dict__)
    return module


def check_run(identifier=1, app=123, commit=COMMIT, status="completed", conclusion="success"):
    return {
        "id": identifier,
        "app": {"id": app},
        "head_sha": commit,
        "name": CHECK_NAME,
        "status": status,
        "conclusion": conclusion,
        "html_url": f"https://github.com/checks/{identifier}",
    }


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.gate = load_gate()

    def run_gate(self, pages, branch_commits=None):
        commits = iter(branch_commits or [COMMIT, COMMIT])

        def api(endpoint, paginate=False):
            if "/git/ref/" in endpoint:
                return {"object": {"type": "commit", "sha": next(commits)}}
            self.assertTrue(paginate)
            self.assertIn(f"/commits/{COMMIT}/check-runs?", endpoint)
            return pages

        with (
            mock.patch.object(self.gate, "api", side_effect=api),
            mock.patch.object(self.gate.time, "monotonic", side_effect=[0, 1, 2, 3]),
            mock.patch.object(self.gate.time, "sleep"),
        ):
            return self.gate.wait_for_check("Azure/k8s-deploy", BRANCH, COMMIT, CHECK_NAME, 123, 3)

    def test_trusted_result_can_be_on_a_later_page(self):
        result = self.run_gate([
            {"check_runs": [check_run(identifier=99, app=999)]},
            {"check_runs": [check_run(identifier=2)]},
        ])
        self.assertEqual(result, "https://github.com/checks/2")

    def test_wrong_app_or_commit_cannot_satisfy_gate(self):
        for result in [check_run(app=999), check_run(commit="b" * 40)]:
            with self.subTest(result=result), self.assertRaises(TimeoutError):
                self.run_gate([{"check_runs": [result]}])

    def test_missing_result_times_out(self):
        with self.assertRaises(TimeoutError):
            self.run_gate([{"check_runs": []}])

    def test_newer_failed_or_cancelled_run_overrides_old_success(self):
        for conclusion in ["failure", "cancelled"]:
            with self.subTest(conclusion=conclusion), self.assertRaises(ValueError):
                self.run_gate([{"check_runs": [
                    check_run(), check_run(identifier=2, conclusion=conclusion)
                ]}])

    def test_newer_pending_run_does_not_reuse_old_success(self):
        with self.assertRaises(TimeoutError):
            self.run_gate([{"check_runs": [
                check_run(), check_run(identifier=2, status="in_progress", conclusion=None)
            ]}])

    def test_branch_moved_after_success_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no longer matches"):
            self.run_gate([{"check_runs": [check_run()]}], [COMMIT, "b" * 40])

    def test_missing_identity_or_invalid_candidate_fails_before_api(self):
        for change in [
            {"REQUIRED_CHECK_APP_ID": "0"},
            {"REQUIRED_CHECK_NAME": ""},
            {"CANDIDATE_COMMIT": "main"},
            {"CANDIDATE_BRANCH": "main"},
            {"CHECK_TIMEOUT_MINUTES": "0"},
            {"CANDIDATE_VERSION": "v7.0.2-rc.1", "CANDIDATE_BRANCH": "releases/v7.0.2-rc.1"},
        ]:
            with (
                self.subTest(change=change),
                mock.patch.dict(os.environ, {**ENVIRONMENT, **change}, clear=True),
                mock.patch.object(self.gate, "api") as api,
                self.assertRaises(ValueError),
            ):
                self.gate.main()
            api.assert_not_called()

    def test_entrypoint_waits_for_pending_check_to_succeed(self):
        checks = iter([
            check_run(status="in_progress", conclusion=None),
            check_run(status="completed"),
        ])

        def api(endpoint, paginate=False):
            if "/git/ref/" in endpoint:
                return {"object": {"type": "commit", "sha": COMMIT}}
            return [{"check_runs": [next(checks)]}]

        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / "summary"
            with (
                mock.patch.dict(os.environ, {**ENVIRONMENT, "GITHUB_STEP_SUMMARY": str(summary)}, clear=True),
                mock.patch.object(self.gate, "api", side_effect=api),
                mock.patch.object(self.gate.time, "sleep") as sleep,
            ):
                self.gate.main()
            sleep.assert_called_once()
            self.assertIn(COMMIT, summary.read_text())
            self.assertIn("https://github.com/checks/1", summary.read_text())

    def test_api_failure_cannot_turn_into_success(self):
        with (
            mock.patch.object(self.gate.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "gh", stderr="HTTP 403")),
            self.assertRaisesRegex(RuntimeError, "GitHub API request failed: HTTP 403"),
        ):
            self.gate.wait_for_check("Azure/k8s-deploy", BRANCH, COMMIT, CHECK_NAME, 123, 3)


class PublishCommitTests(unittest.TestCase):
    def normalize(self, expected, actual=COMMIT, tag_conflict=False):
        text = (WORKFLOWS / "create_release.yaml").read_text()
        script = text.split("      - id: normalize\n", 1)[1].split("        run: |\n", 1)[1]
        script = script.split("\n      - uses:", 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git = root / "git"
            git.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = ls-remote ]; then\n"
                "  printf '%s\\trefs/heads/releases/v7.0.2\\n' \"$TEST_REF_SHA\"\n"
                "elif [ \"$1\" = push ]; then\n"
                "  test \"$3\" = \"$EXPECTED_COMMIT:refs/tags/$RELEASE_VERSION\" || exit 99\n"
                "  exit \"$TEST_TAG_CONFLICT\"\n"
                "else exit 99; fi\n"
            )
            git.chmod(0o755)
            output = root / "output"
            result = subprocess.run(
                ["bash", "-c", textwrap.dedent(script)],
                env={
                    **os.environ,
                    "PATH": str(root) + os.pathsep + os.environ["PATH"],
                    "INPUT_BRANCH": f"refs/heads/{BRANCH}",
                    "EXPECTED_COMMIT": expected,
                    "RELEASE_VERSION": "v7.0.2",
                    "TEST_REF_SHA": actual,
                    "TEST_TAG_CONFLICT": "1" if tag_conflict else "0",
                    "GITHUB_OUTPUT": str(output),
                },
                capture_output=True, text=True, timeout=10,
            )
            return result, output.read_text() if output.exists() else ""

    def test_existing_ungated_callers_keep_branch_normalization(self):
        result, output = self.normalize("")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, f"commit={BRANCH}\n")

    def test_gated_publication_targets_exact_commit(self):
        result, output = self.normalize(COMMIT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, f"commit={COMMIT}\n")

    def test_changed_branch_prevents_publication(self):
        result, output = self.normalize(COMMIT, actual="b" * 40)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output, "")

    def test_conflicting_version_tag_prevents_publication(self):
        result, output = self.normalize(COMMIT, tag_conflict=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output, "")


if __name__ == "__main__":
    unittest.main()
