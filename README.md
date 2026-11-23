# action-release-workflows

[![Latest Release](https://img.shields.io/github/v/release/Azure/action-release-workflows?label=Latest%20Release)](https://github.com/Azure/action-release-workflows/releases/latest)
[![GitHub License](https://img.shields.io/github/license/Azure/action-release-workflows)](LICENSE)
[![GitHub Issues](https://img.shields.io/github/issues/Azure/action-release-workflows)](https://github.com/Azure/action-release-workflows/issues)

Reusable GitHub Actions workflows for automated releases. Includes AI-powered version classification, signed commits, changelog generation, and release PR creation.

## Workflows

| Workflow | Trigger | Description |
|----------|---------|-------------|
| `release-proposal.yaml` | `workflow_call` | Reusable: scans merged PRs, classifies version bump via AI, creates a release PR |
| `release-proposal-dispatch.yaml` | Schedule (Mon 9am UTC) / `workflow_dispatch` | Thin wrapper that calls `release-proposal.yaml` for this repo |
| `release.yaml` | Push to `main` (CHANGELOG.md) / `workflow_dispatch` | Extracts changelog, creates GitHub release |
| `extract_changelog.yaml` | `workflow_call` | Reusable: parses CHANGELOG.md for version + body |
| `create_release.yaml` | `workflow_call` | Reusable: creates a GitHub release with tag |
| `check_signed_commits.yaml` | `workflow_call` | Reusable: verifies all PR commits are signed |
| `release_js_project.yaml` | `workflow_call` | Reusable: full JS project release (changelog, branch, release, major tag) |
| `create_js_branch.yaml` | `workflow_call` | Reusable: creates a release branch with built JS artifacts |
| `check_release_candidate.yaml` | `workflow_call` | Reusable: validates the candidate and waits for a check from an approved GitHub App |
| `publish_js_project.yaml` | `workflow_call` | Reusable: publishes the prepared commit only after the trusted check succeeds |
| `switch_js_branch.yaml` | `workflow_call` | Reusable: switches/creates a release branch (e.g. nightly) |
| `nightly_release.yaml` | `workflow_call` | Reusable: nightly release to `releases/nightly` branch |

## Release Proposal Workflow

The `release-proposal.yaml` workflow generates a **release PR for manual review** — it suggests a version bump with justification, but no release is created until a human reviews and merges the PR. Features:

- **AI-powered version suggestion** using [`actions/ai-inference`](https://github.com/actions/ai-inference) to analyze merged PRs and suggest `patch`, `minor`, or `major` bumps, with reasoning included in the PR body
- **Dependabot auto-detection** — if all merged PRs are from dependabot, automatically selects `patch`
- **Signed commits** — uses the GitHub API to create commits (automatically signed by GitHub)
- **CHANGELOG.md generation** — adds a new version entry with categorized PR links
- **package.json / package-lock.json version bumps** — detects and updates if present
- **Stale PR cleanup** — closes any existing release PRs before creating a new one

### Usage: Manual Dispatch

Trigger from the Actions tab or via CLI:

```bash
# Let AI decide the version bump
gh workflow run "Release Proposal"

# Override with a specific version type
gh workflow run "Release Proposal" -f version_type=minor

# Specify a custom changelog path
gh workflow run "Release Proposal" -f version_type=patch -f changelog_path=./docs/CHANGELOG.md
```

### Usage: Reusable Workflow

Call from your repository's workflow:

```yaml
name: Release Proposal

on:
  schedule:
    - cron: '0 9 * * 1'
  workflow_dispatch:
    inputs:
      version_type:
        description: 'Version bump type'
        required: false
        type: choice
        options:
          - ''
          - patch
          - minor
          - major
      changelog_path:
        description: 'Path to CHANGELOG.md'
        required: false
        default: './CHANGELOG.md'
        type: string

jobs:
  release-proposal:
    uses: Azure/action-release-workflows/.github/workflows/release-proposal.yaml@main
    with:
      version_type: ${{ inputs.version_type || '' }}
      changelog_path: ${{ inputs.changelog_path || './CHANGELOG.md' }}
    permissions:
      models: read
      contents: write
      pull-requests: write
```

### Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `version_type` | No | `''` (AI decides) | Override version bump: `patch`, `minor`, or `major` |
| `changelog_path` | No | `./CHANGELOG.md` | Path to the changelog file |

### How It Works

1. Finds the latest `v*` tag and queries all PRs merged since then
2. Classifies PRs as dependabot vs non-dependabot
3. Determines version bump:
   - **Manual override** (`version_type` input) takes highest priority
   - **All dependabot** PRs = automatic `patch`
   - **Non-dependabot** PRs = AI inference via `actions/ai-inference` (falls back to `minor` if AI fails)
4. Computes new semver version
5. Updates `CHANGELOG.md` with categorized PR entries
6. Bumps `package.json` and `package-lock.json` (if they exist)
7. Creates a **signed commit** via the GitHub REST API (tree + blob + commit)
8. Opens a PR from `automated-release/v<version>` to `main` with version reasoning, source PRs, and bump justification for reviewer approval

### Permissions Required

```yaml
permissions:
  models: read        # For AI inference
  contents: write     # For creating branches and commits
  pull-requests: write # For creating PRs
```

## Other Reusable Workflows

### Extract Changelog

```yaml
jobs:
  changelog:
    uses: <owner>/<repo>/.github/workflows/extract_changelog.yaml@main
    with:
      changelogPath: ./CHANGELOG.md
```

**Outputs:** `version`, `body`, `prerelease`

### Create Release

```yaml
jobs:
  release:
    uses: <owner>/<repo>/.github/workflows/create_release.yaml@main
    with:
      branch: ${{ github.ref }}
      version: v1.2.3
      body: "Release notes here"
      prerelease: false
```

### Check Signed Commits

```yaml
jobs:
  signed:
    uses: <owner>/<repo>/.github/workflows/check_signed_commits.yaml@main
```

Verifies all commits in a PR are signed. Posts a comment listing unsigned commits if any are found.

### Prepare, validate, and publish a JS release

`release_js_project.yaml` keeps its existing automatic publication behavior unless
`prepareOnly: true` is supplied. Preparation returns `branch`, `commit`, `version`,
and `body`. The commit is recorded after the release bundle is built, committed,
and pushed, not before the build. Existing preparation steps and the default
publishing, major-tag, and prerelease behavior are preserved. Existing callers
do not need Azure DevOps configuration or additional token permissions.

For a protected release, separate preparation from publication:

```text
Prepare built commit
        |
Trusted bridge runs the external test for that commit
        |
GitHub check from the approved App on that commit
        |
publish_js_project.yaml validates the result and publishes that commit
```

The following is an activation example. Replace `REVIEWED_COMMIT_SHA` with the
reviewed shared-workflow commit only after the external bridge is configured.
It is not a working bridge or an Azure DevOps trigger.
Keep the existing publisher until preparation, the automatic trusted test
trigger, and gated publication can be switched together. Do not activate an
intermediate preparation-only caller. The bridge must automatically queue the
test after approved preparation; waiting for a result does not itself start it.

```yaml
jobs:
  prepare:
    permissions:
      actions: read
      contents: write
    uses: Azure/action-release-workflows/.github/workflows/release_js_project.yaml@REVIEWED_COMMIT_SHA
    with:
      changelogPath: ./CHANGELOG.md
      prepareOnly: true
  publish:
    needs: prepare
    if: needs.prepare.outputs.commit != ''
    permissions:
      contents: write
      checks: read
    uses: Azure/action-release-workflows/.github/workflows/publish_js_project.yaml@REVIEWED_COMMIT_SHA
    with:
      branch: ${{ needs.prepare.outputs.branch }}
      commit: ${{ needs.prepare.outputs.commit }}
      version: ${{ needs.prepare.outputs.version }}
      body: ${{ needs.prepare.outputs.body }}
      checkName: '1ES private-cluster release gate'
      checkAppId: ${{ fromJSON(vars.PRIVATE_CLUSTER_GATE_APP_ID || '0') }}
      timeoutMinutes: 90
```

The gated publisher requires a nonempty check name and a positive GitHub App ID.
There is no ungated fallback in `publish_js_project.yaml`. It accepts only the
latest matching check run from that App on the candidate SHA, with a completed
`success` conclusion. Commit statuses or checks from other Apps cannot satisfy it.
Missing results time out; newer failed, cancelled, or pending runs do not reuse an
older success. The timeout must be between 1 and 120 minutes.
This opt-in private-cluster flow supports stable `vX.Y.Z` releases, matching the
1ES candidate checks. It does not introduce prerelease publishing behavior.

The release branch must still match the candidate. Publication uses the full SHA
rather than a branch name, and major-tag publication also checks the version tag.
A branch change detected before publication stops the job; pinning the tag target
to the SHA prevents a later branch movement from selecting untested code.

Only the new gated publisher uses the stricter tag update. It verifies the
release branch and version tag, reads the current major-tag object, and replaces
that single remote ref with an explicit `--force-with-lease=<ref>:<old-object>` guard.
It never deletes the remote major tag first. A rejected push leaves the existing
tag in place, and a concurrent change rejects the update instead of being overwritten.
For a new major tag, the empty expected object requires the ref to remain absent.
Version tags are not force-updated.

The optional `expectedCommit` input to `create_release.yaml` also applies only
when explicitly supplied. The existing automatic release workflow does not set
it or call the new gate/tag helpers. General hardening of the legacy publisher
and corrections to its prerelease behavior are separate changes, not part of
this opt-in integration.

The trusted bridge is external to these workflows. It must authorize the
preparation run and approved source revision, queue the exact built candidate
using a governed definition, and report a SHA-bound check using the configured
App. Branch activity or a caller-provided SHA is not authorization to run
privileged code. Define pipeline/service-connection checks and queue permissions
outside candidate-controlled YAML. Failed or cancelled external runs must be
reported, not silently omitted. These workflows grant no Azure permissions and do
not queue Azure DevOps pipelines.

For the k8s-deploy 1ES pipeline, select the reviewed definition revision as the
Azure DevOps `self` repository revision. Pass the preparation outputs separately
as `releaseCandidateBranch` and `releaseCandidateCommit`. The pipeline checks out
that candidate in a separate directory; its `Build.SourceVersion` identifies the
definition revision, not the action being tested. Do not load pipeline YAML or
cleanup scripts from the candidate checkout.

Run the local contract tests with:

```bash
python3 -B -m unittest discover -s tests -v
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to contribute, the release process, and the CLA requirement.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft 
trademarks or logos is subject to and must follow 
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
