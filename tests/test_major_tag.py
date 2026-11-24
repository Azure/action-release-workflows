import json
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMMIT = "a" * 40
PREVIOUS = "b" * 40
REPLACEMENT = "c" * 40
CONCURRENT = "d" * 40

GIT_STUB = """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

state_file = Path(os.environ['FAKE_GIT_STATE'])
state = json.loads(state_file.read_text())
args = sys.argv[1:]
state['calls'].append(args)

def finish(code=0):
    state_file.write_text(json.dumps(state))
    sys.exit(code)

if args[:3] == ['ls-remote', '--heads', 'origin']:
    print(state['branch'] + '\\trefs/heads/releases/v7.0.2')
    finish()
if args == ['fetch', '--no-tags', 'origin', 'refs/tags/v7.0.2']:
    finish()
if args == ['rev-parse', 'FETCH_HEAD^{commit}']:
    print(state['version_tag'])
    finish()
if args == ['ls-remote', '--refs', 'origin', 'refs/tags/v7']:
    if state['mode'] == 'lookup_failure':
        print('fixture: tag lookup failed', file=sys.stderr)
        finish(1)
    if state['remote'] is not None:
        print(state['remote'] + '\\trefs/tags/v7')
    finish()
if args[0] == 'config':
    finish()
if args == ['show-ref', '--verify', '--quiet', 'refs/tags/v7']:
    finish(0 if state['local_tag'] else 1)
if args == ['tag', '--delete', 'v7']:
    state['local_tag'] = None
    finish()
if args == ['tag', '-a', 'v7', state['candidate'], '-m', 'Latest v7 Release']:
    state['local_tag'] = state['replacement']
    finish()
if args[0] == 'push':
    prefix = '--force-with-lease=refs/tags/v7:'
    if len(args) != 4 or not args[1].startswith(prefix) or args[2:] != ['origin', 'refs/tags/v7:refs/tags/v7']:
        print('fixture: unexpected or unguarded push', file=sys.stderr)
        finish(99)
    if state['mode'] == 'push_failure':
        print('fixture: update failed', file=sys.stderr)
        finish(1)
    if state['mode'] == 'concurrent_change':
        state['remote'] = state['concurrent']
    if args[1][len(prefix):] != (state['remote'] or ''):
        print('fixture: lease rejected', file=sys.stderr)
        finish(1)
    state['remote'] = state['local_tag']
    state['published_commit'] = state['candidate']
    finish()
print('fixture: unexpected Git command', file=sys.stderr)
finish(99)
"""


class MajorTagTests(unittest.TestCase):
    def run_update(self, mode="success", previous=PREVIOUS, branch=COMMIT,
                   version_tag=COMMIT, local_tag=False):
        workflow = (ROOT / ".github/workflows/publish_js_project.yaml").read_text()
        script = textwrap.dedent(workflow.split("        run: |\n", 1)[1])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git = root / "git"
            git.write_text(GIT_STUB)
            git.chmod(0o755)
            state_file = root / "state.json"
            state_file.write_text(json.dumps({
                "calls": [], "mode": mode, "remote": previous, "branch": branch,
                "version_tag": version_tag, "candidate": COMMIT,
                "local_tag": PREVIOUS if local_tag else None,
                "replacement": REPLACEMENT, "concurrent": CONCURRENT,
            }))
            result = subprocess.run(
                ["bash", "-c", script], cwd=root,
                env={
                    **os.environ,
                    "PATH": str(root) + os.pathsep + os.environ["PATH"],
                    "FAKE_GIT_STATE": str(state_file),
                    "RELEASE_BRANCH": "releases/v7.0.2",
                    "CANDIDATE_COMMIT": COMMIT,
                    "RELEASE_VERSION": "v7.0.2",
                },
                capture_output=True, text=True, timeout=10,
            )
            return result, json.loads(state_file.read_text())

    def test_success_uses_one_guarded_update_without_remote_deletion(self):
        for cached in [False, True]:
            with self.subTest(local_tag=cached):
                result, state = self.run_update(local_tag=cached)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(state["remote"], REPLACEMENT)
                self.assertEqual(state["published_commit"], COMMIT)
                pushes = [call for call in state["calls"] if call[0] == "push"]
                self.assertEqual(pushes, [[
                    "push", f"--force-with-lease=refs/tags/v7:{PREVIOUS}",
                    "origin", "refs/tags/v7:refs/tags/v7",
                ]])

    def test_failed_update_keeps_the_old_remote_tag(self):
        result, state = self.run_update(mode="push_failure")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(state["remote"], PREVIOUS)

    def test_concurrent_change_is_not_overwritten(self):
        for previous in [PREVIOUS, None]:
            with self.subTest(previous=previous):
                result, state = self.run_update(mode="concurrent_change", previous=previous)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(state["remote"], CONCURRENT)
                self.assertIn("lease rejected", result.stderr)

    def test_first_creation_requires_the_remote_tag_to_remain_absent(self):
        result, state = self.run_update(previous=None)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(state["remote"], REPLACEMENT)
        push = next(call for call in state["calls"] if call[0] == "push")
        self.assertEqual(push[1], "--force-with-lease=refs/tags/v7:")

    def test_branch_or_version_tag_mismatch_stops_before_push(self):
        for change in [{"branch": CONCURRENT}, {"version_tag": CONCURRENT}]:
            with self.subTest(change=change):
                result, state = self.run_update(**change)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(state["remote"], PREVIOUS)
                self.assertFalse(any(call[0] == "push" for call in state["calls"]))

    def test_lookup_failure_stops_before_push(self):
        result, state = self.run_update(mode="lookup_failure")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(state["remote"], PREVIOUS)
        self.assertFalse(any(call[0] == "push" for call in state["calls"]))


if __name__ == "__main__":
    unittest.main()
