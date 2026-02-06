# Release Workflows

[![Latest Release](https://img.shields.io/github/v/release/Azure/action-release-workflows?label=Latest%20Release)](https://github.com/Azure/action-release-workflows/releases/latest)
[![GitHub License](https://img.shields.io/github/license/Azure/action-release-workflows)](LICENSE)
[![GitHub Issues](https://img.shields.io/github/issues/Azure/action-release-workflows)](https://github.com/Azure/action-release-workflows/issues)

Reusable GitHub Actions workflows for automating releases and enforcing commit policies.

## Available Workflows

| Workflow | Description |
|----------|-------------|
| `release_js_project.yaml` | Full release workflow for JS projects (changelog extraction, branch creation, release, major tag update) |
| `check_signed_commits.yaml` | Verifies all PR commits are signed, comments on violations |
| `extract_changelog.yaml` | Parses CHANGELOG.md and outputs version/body/prerelease status |
| `create_release.yaml` | Creates a GitHub release with specified version and body |
| `create_js_branch.yaml` | Creates a release branch with built JS artifacts |
| `nightly_release.yaml` | Creates nightly releases from main branch |
| `switch_js_branch.yaml` | Switches to or creates a nightly release branch |

## How Release Workflows Work

The release workflow is triggered when changes are pushed to the main branch and there are updates in the CHANGELOG.md file. When a new release is initiated, the workflow executes the following steps:

1. Parses the CHANGELOG.md file to extract the release notes and identifies the most recent version.
2. Checks if a tag for the latest version already exists. If found, subsequent workflows are halted to avoid duplication.
3. If no existing tag, creates a new branch from main named `releases/v<version>`.
4. Publishes the release to GitHub with the corresponding version tag.
5. Updates the major version tag (e.g., `v1`) to point to the latest release.

## Usage

### Release JS Project

1. Create a CHANGELOG.md file following [Keep a Changelog](https://keepachangelog.com/) format.

2. Create a workflow file in your project:

```yaml
name: release project

on:
  push:
    branches:
      - main
    paths:
      - CHANGELOG.md
  workflow_dispatch:

jobs:
  release:
    uses: Azure/action-release-workflows/.github/workflows/release_js_project.yaml@main
    permissions:
      actions: read
      contents: write
    with:
      changelogPath: ./CHANGELOG.md
```

The workflow triggers automatically when CHANGELOG.md changes are pushed to main, or manually via GitHub Actions UI.

### Check Signed Commits

Enforces GPG/SSH signed commits on pull requests. Comments on PRs with unsigned commits and fails the check.

```yaml
name: Check Signed Commits

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  check-signatures:
    uses: Azure/action-release-workflows/.github/workflows/check_signed_commits.yaml@main
    permissions:
      pull-requests: write
```

Features:
- Lists all unsigned commits in PR
- Posts/updates a comment identifying unsigned commits
- Removes comment when all commits are signed
- Fails the check if any unsigned commits exist

### Nightly Release

For automated nightly builds:

```yaml
name: nightly

on:
  schedule:
    - cron: '0 0 * * *'
  workflow_dispatch:

jobs:
  nightly:
    uses: Azure/action-release-workflows/.github/workflows/nightly_release.yaml@main
    permissions:
      contents: write
```

## Contributing

This project welcomes contributions and suggestions. Most contributions require you to agree to a
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
