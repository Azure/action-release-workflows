# Contributing

This project welcomes contributions and suggestions. Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Pull Requests

1. Fork the repo and create your branch from `main`.
2. All commits must be signed. The repo runs a [signed commit check](.github/workflows/check_signed_commits.yaml) on every PR. See [GitHub's guide on signing commits](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits).
3. Open a pull request against `main`.

## Release Process

Releases are automated via GitHub Actions workflows:

### 1. Release Proposal (automated)

The [Release Proposal Dispatch](.github/workflows/release-proposal-dispatch.yaml) workflow runs on a schedule (Mondays at 9am UTC) or can be triggered manually:

```bash
# Let AI decide the version bump
gh workflow run "Release Proposal Dispatch"

# Override with a specific version type
gh workflow run "Release Proposal Dispatch" -f version_type=minor
```

This workflow:
- Scans all PRs merged since the last `v*` tag
- Classifies the version bump (patch/minor/major) using AI inference, or auto-selects `patch` for dependabot-only changes
- Updates `CHANGELOG.md` with categorized PR entries
- Bumps `package.json` / `package-lock.json` if present
- Creates a signed commit and opens a release PR

### 2. Release (on merge)

The [Release](.github/workflows/release.yaml) workflow triggers automatically when `CHANGELOG.md` is pushed to `main` (i.e., when a release PR merges). It can also be triggered manually:

```bash
gh workflow run "release"
```

This workflow:
- Extracts the latest version and body from `CHANGELOG.md`
- Checks if a Git tag for that version already exists
- Creates a GitHub release with the tag if it doesn't exist

### Changelog Format

The changelog follows this format and is parsed by the release workflow:

```markdown
## [x.y.z] - YYYY-MM-DD
- Description of change
- #PR_NUMBER Description of another change
```

Entries are added automatically by the release proposal workflow, but can also be edited manually before merging the release PR.
