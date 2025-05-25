# paprika-ha

An unofficial [Home Assistant](https://www.home-assistant.io/) Integration for Paprika Recipe Manager.

## Features

### Meal Plans

The integration exposes a Calendar Entity for each of the meal types in the app.

### Grocery Lists

The integration exposes a grocery list as a 'todo list' in Home Assistant. For now this is read only, and items from all the lists you have in the app are combined. 

## Installing

1. Go to HACS, select "Custom Repositories" and add this repository as a Custom Repository. [More info on the process is available on the HACS Website](https://hacs.xyz/docs/faq/custom_repositories/).

2. Open the integration inside HACS:<br>
   [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?repository=paprika-ha&owner=rbrunt)

4. Install the integration, restart Home Assistant

5. Under "Devices and Service", set up "Paprika", enter your username and password, and you're done!
