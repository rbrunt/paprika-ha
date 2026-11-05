import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import aiohttp
import homeassistant.util.dt
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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
    _recipes: dict["RecipeID", "Recipe"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._recipes = {}

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
        recipes = await self._async_update_recipes(meals)
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

        Only recipes that are new or whose hash changed are fetched. A failure
        here keeps the previously cached recipes rather than failing the update,
        since the calendars still work without recipe details.
        """
        client = self.config_entry.runtime_data.client
        cutoff = homeassistant.util.dt.now().date() - RECIPE_LOOKBACK
        wanted = {
            m["recipe_uid"] for m in meals if m["recipe_uid"] and m["date"] >= cutoff
        }

        try:
            hashes = await client.get_recipe_hashes()
        except aiohttp.ClientError as err:
            _LOGGER.warning(
                "Could not fetch recipe list, keeping cached recipes: %s", err
            )
            return {uid: r for uid, r in self._recipes.items() if uid in wanted}

        recipes: dict[RecipeID, Recipe] = {}
        for uid in wanted:
            cached = self._recipes.get(uid)
            if uid not in hashes:
                # Planned meal points at a recipe that no longer exists.
                continue
            if cached and cached.get("hash") == hashes[uid]:
                recipes[uid] = cached
                continue
            try:
                recipes[uid] = await client.get_recipe(uid)
            except aiohttp.ClientError as err:
                _LOGGER.warning("Could not fetch recipe %s: %s", uid, err)
                if cached:
                    recipes[uid] = cached

        self._recipes = recipes
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
                if existing_index is not None:
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
