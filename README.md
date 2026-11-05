# paprika-ha

An unofficial [Home Assistant](https://www.home-assistant.io/) Integration for Paprika Recipe Manager.

## Features

### Meal Plans

The integration exposes a Calendar Entity for each of the meal types in the app. Meals on the same day are listed in the order they are planned in Paprika, so a main dish comes before its sides.

#### Recipes in calendar events (optional)

Turn on **Show recipes in calendar events** under the integration's **Configure** button (Settings → Devices & services → Paprika) to put each planned meal's recipe in its calendar event description: prep and cook times, servings, ingredients, directions, notes and a link to the original recipe. Meals added as notes, without a recipe, keep just their name. It is off by default.

**Note:** The description is HTML, so this works best with calendar cards that render HTML, such as the [Week Planner card](https://github.com/FamousWolf/week-planner-card), which shows it when you tap an event. Home Assistant's own calendar and most other calendar cards show the HTML tags as plain text.

Recipes are fetched for meals planned from two weeks ago onward, and only re-fetched when they change in Paprika.

### Grocery Lists

The integration exposes each grocery list from your Paprika account as a 'todo list' entity in Home Assistant. 

**Note:** Due to how Paprika's API works, deleting an item marks it purchased in the paprika app.

## Installing

The integration is available in [HACS](https://hacs.xyz). After you've installed HACS, simply:

1. Go to HACS, search for 'paprika', and install the extension. Restart Home Assistant. Alternatively, you can click this link to go straight there: [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rbrunt&repository=paprika-ha)

2. Under "Devices and Service", set up "Paprika", enter your username and password, and you're done!


## Developing

See [DEVELOPING](./DEVELOPING.md) for notes on developing the integration.
