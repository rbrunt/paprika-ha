# Notes for developing the integration

This repository is a pretty standard home assistant integration repository. The easiest way to get started is to clone it and use the 'devcontainer' in vscode to get your environment set up.

There isn't much documentation about the Paprika API, but there is a [useful thread here](https://gist.github.com/mattdsteele/7386ec363badfdeaad05a418b9a1f30a) that has some details, and was a great help in the initial implementation.

## Common tasks

To get HACS to show an update being available, a new version needs to be published. Run the helper script from the `main` branch with a clean, up-to-date checkout (requires [`uv`](https://docs.astral.sh/uv/) and the `gh` CLI):

```bash
scripts/bump_version_and_release
```

It shows an arrow-key menu to pick a patch, minor or major release, then shows the before/after version and asks for confirmation. On confirmation it bumps the version in `custom_components/paprika/manifest.json`, commits and pushes it, and creates a **draft** GitHub release (tag `vX.Y.Z`, with auto-generated notes). Edit the notes on GitHub and publish it when you're ready; the tag is created at publish time.

Pass `patch`, `minor` or `major` to skip the menu, or `--dry-run` to preview the new version without changing anything. The script's dependencies (`questionary`, `rich`) are declared inline, so `uv` installs them automatically.
