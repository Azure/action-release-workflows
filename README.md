# action-release-workflows

[![Latest Release](https://img.shields.io/github/v/release/Azure/action-release-workflows?label=Latest%20Release)](https://github.com/Azure/action-release-workflows/releases/latest)
[![GitHub License](https://img.shields.io/github/license/Azure/action-release-workflows)](LICENSE)
[![GitHub Issues](https://img.shields.io/github/issues/Azure/action-release-workflows)](https://github.com/Azure/action-release-workflows/issues)

Reusable GitHub Actions workflows for automated releases. Includes AI-powered version classification, signed commits, changelog generation, and release PR creation.

## Workflows

| Workflow | Trigger | Description |
|----------|---------|-------------|
| `release-proposal.yml` | `workflow_call` | Reusable: scans merged PRs, classifies version bump via AI, creates a release PR |
| `release-proposal-dispatch.yml` | Schedule (Mon 9am UTC) / `workflow_dispatch` | Thin wrapper that calls `release-proposal.yml` for this repo |
| `release.yaml` | Push to `main` (CHANGELOG.md) / `workflow_dispatch` | Extracts changelog, creates GitHub release |
| `extract_changelog.yaml` | `workflow_call` | Reusable: parses CHANGELOG.md for version + body |
| `create_release.yaml` | `workflow_call` | Reusable: creates a GitHub release with tag |
| `check_signed_commits.yaml` | `workflow_call` | Reusable: verifies all PR commits are signed |
| `release_js_project.yaml` | `workflow_call` | Reusable: full JS project release (changelog, branch, release, major tag) |
| `create_js_branch.yaml` | `workflow_call` | Reusable: creates a release branch with built JS artifacts |
| `switch_js_branch.yaml` | `workflow_call` | Reusable: switches/creates a release branch (e.g. nightly) |
| `nightly_release.yaml` | `workflow_call` | Reusable: nightly release to `releases/nightly` branch |

## Release Proposal Workflow

The `release-proposal.yml` workflow automates the creation of release PRs with:

- **AI-powered version classification** using [`actions/ai-inference`](https://github.com/actions/ai-inference) to analyze merged PRs and suggest `patch`, `minor`, or `major` bumps
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
    uses: Azure/action-release-workflows/.github/workflows/release-proposal.yml@main
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
8. Opens a PR from `automated-release/v<version>` to `main`

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

## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft 
trademarks or logos is subject to and must follow 
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
