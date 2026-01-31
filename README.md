# paprika-ha

An unofficial [Home Assistant](https://www.home-assistant.io/) Integration for Paprika Recipe Manager.

## Features

### Meal Plans

The integration exposes a Calendar Entity for each of the meal types in the app.

### Grocery Lists

The integration exposes a grocery list as a 'todo list' in Home Assistant. For now this is read only, and items from all the lists you have in the app are combined.

## Installing

The integration is available in [HACS](https://hacs.xyz). After you've installed HACS, simply:

1. Go to HACS, search for 'paprika', and install the extension. Restart Home Assistant. Alternatively, you can click this link to go straight there: [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rbrunt&repository=paprika-ha)

2. Under "Devices and Service", set up "Paprika", enter your username and password, and you're done!


## Developing

This repository is a pretty standard home assistant integration repository. The easiest way to get started is to clone it and use the 'devcontainer' in vscode to get your environment set up.

There isn't much documentation about the Paprika API, but there is a [useful thread here](https://gist.github.com/mattdsteele/7386ec363badfdeaad05a418b9a1f30a) that has some details, and was a great help in the initial implementation.
