import asyncio
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import aiohttp
import homeassistant.util.dt
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_RECIPE_FORMAT, DEFAULT_RECIPE_FORMAT, RECIPE_FORMAT_NONE

if TYPE_CHECKING:
    from .api import (
        GroceryList,
        GroceryListItem,
        MealType,
        PlannedMeal,
        Recipe,
        RecipeID,
        SyncStatus,
    )
    from .data import PaprikaConfigEntry

_LOGGER = logging.getLogger(__name__)

# Recipes are only fetched for meals planned on or after this many days ago,
# so a long meal-plan history doesn't mean fetching every recipe ever planned.
RECIPE_LOOKBACK = timedelta(days=14)

# Adding an item waits on the aisle lookup, so don't let a slow API hold it up.
AISLE_LOOKUP_TIMEOUT = 10  # seconds


@dataclass
class PaprikaData:
    status: "SyncStatus"
    meals: list["PlannedMeal"]
    groceries: list["GroceryListItem"]
    meal_types: list["MealType"]
    grocery_lists: list["GroceryList"]
    recipes: dict["RecipeID", "Recipe"] = field(default_factory=dict)


class PaprikaCoordinator(DataUpdateCoordinator[PaprikaData]):
    """Class to manage fetching data from the API."""

    config_entry: "PaprikaConfigEntry"
    last_status: "SyncStatus | None" = None

    async def _async_update_data(self) -> Any:
        """Update data via library."""
        # Fetch current status to check if anything has changed
        current_status = await self.config_entry.runtime_data.client.get_status()

        # Only proceed with updating entities if status has changed
        if self.last_status == current_status:
            # Return the existing data without re-fetching
            return self.data

        # Status has changed, fetch updated data
        self.last_status = current_status
        meal_types = await self.config_entry.runtime_data.client.get_meal_types()
        meals = await self.config_entry.runtime_data.client.get_meals(meal_types)
        groceries = await self.config_entry.runtime_data.client.get_groceries()
        grocery_lists = await self.config_entry.runtime_data.client.get_grocery_lists()
        recipe_format = self.config_entry.options.get(
            CONF_RECIPE_FORMAT, DEFAULT_RECIPE_FORMAT
        )
        recipes = (
            {}
            if recipe_format == RECIPE_FORMAT_NONE
            else await self._async_update_recipes(meals)
        )
        return PaprikaData(
            status=current_status,
            meal_types=meal_types,
            meals=meals,
            groceries=groceries,
            grocery_lists=grocery_lists,
            recipes=recipes,
        )

    async def _async_update_recipes(
        self, meals: list["PlannedMeal"]
    ) -> dict["RecipeID", "Recipe"]:
        """
        Fetch the recipes behind recently planned meals.

        A failure or timeout here keeps the recipes from the last update rather
        than failing it, since the calendars still work without recipe details.
        It also clears the last sync status, so the next poll retries instead of
        waiting for something to change in Paprika.
        """
        cutoff = homeassistant.util.dt.now().date() - RECIPE_LOOKBACK
        wanted = {
            m["recipe_uid"] for m in meals if m["recipe_uid"] and m["date"] >= cutoff
        }
        try:
            recipes, complete = await self.config_entry.runtime_data.client.get_recipes(
                wanted
            )
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Could not fetch recipes, keeping the last ones: %s", err)
            self.last_status = None
            return self.data.recipes if self.data else {}
        if not complete:
            self.last_status = None
        return recipes

    async def async_save_grocery_items(
        self, items: list["GroceryListItem"]
    ) -> None:
        await self.config_entry.runtime_data.client.save_grocery_items(items)
        if self.data:
            groceries = list(self.data.groceries)
            for item in items:
                existing_index = next(
                    (i for i, g in enumerate(groceries) if g["uid"] == item["uid"]),
                    None,
                )
                if item.get("deleted"):
                    if existing_index is not None:
                        groceries.pop(existing_index)
                elif existing_index is not None:
                    groceries[existing_index] = item
                else:
                    groceries.append(item)
            self.async_set_updated_data(
                PaprikaData(
                    status=self.data.status,
                    meal_types=self.data.meal_types,
                    meals=self.data.meals,
                    groceries=groceries,
                    grocery_lists=self.data.grocery_lists,
                    recipes=self.data.recipes,
                )
            )
        self.last_status = None

    async def async_resolve_aisle(self, ingredient: str) -> tuple[str, str]:
        """Look up the (aisle name, aisle uid) Paprika has for an ingredient.

        Uses Paprika's learned ingredient mapping. Returns empty strings when
        Paprika has no mapping for the ingredient, which leaves the item in
        Miscellaneous.
        """
        client = self.config_entry.runtime_data.client
        try:
            async with asyncio.timeout(AISLE_LOOKUP_TIMEOUT):
                ingredients = await client.get_grocery_ingredients()
                aisles = await client.get_grocery_aisles()
        except Exception as err:  # noqa: BLE001 - never block adding an item on a lookup
            _LOGGER.warning(
                "Could not look up an aisle for %r, adding it without one: %r",
                ingredient,
                err,
            )
            return "", ""
        aisle_names = {a["uid"]: a["name"] for a in aisles}
        by_name = {
            i["name"].strip().lower(): i["aisle_uid"]
            for i in ingredients
            if i.get("aisle_uid") in aisle_names
        }
        key = ingredient.strip().lower()
        for candidate in (key, key.removesuffix("s"), f"{key}s"):
            if candidate in by_name:
                uid = by_name[candidate]
                return aisle_names[uid], uid
        # Paprika hasn't learned this ingredient; leave it in Miscellaneous.
        _LOGGER.debug("No learned aisle for %r", ingredient)
        return "", ""
