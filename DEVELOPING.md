# Notes for developing the integration

This repository is a pretty standard home assistant integration repository. The easiest way to get started is to clone it and use the 'devcontainer' in vscode to get your environment set up.

There isn't much documentation about the Paprika API, but there is a [useful thread here](https://gist.github.com/mattdsteele/7386ec363badfdeaad05a418b9a1f30a) that has some details, and was a great help in the initial implementation.

## Common tasks

To get HACS to show an update being available, a new version needs to be published. Update the integration version in `custom_components/paprika/manifest.json` using the helper script:

```bash
python3 scripts/bump_version [patch|minor|major]
```

Then create a new release in github using the same version number.
