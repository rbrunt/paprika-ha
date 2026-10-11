from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .aisle_keywords import guess_aisle_name

if TYPE_CHECKING:
    from .api import GroceryList, GroceryListItem, MealType, PlannedMeal, SyncStatus
    from .data import PaprikaConfigEntry


@dataclass
class PaprikaData:
    status: "SyncStatus"
    meals: list["PlannedMeal"]
    groceries: list["GroceryListItem"]
    meal_types: list["MealType"]
    grocery_lists: list["GroceryList"]


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
        return PaprikaData(
            status=current_status,
            meal_types=meal_types,
            meals=meals,
            groceries=groceries,
            grocery_lists=grocery_lists,
        )

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
                )
            )

    async def async_resolve_aisle(self, ingredient: str) -> tuple[str, str]:
        """Look up the (aisle name, aisle uid) Paprika has for an ingredient.

        Uses Paprika's learned ingredient mapping first, then a keyword guess.
        Returns empty strings when neither matches, which leaves the item in
        Miscellaneous.
        """
        client = self.config_entry.runtime_data.client
        try:
            ingredients = await client.get_grocery_ingredients()
            aisles = await client.get_grocery_aisles()
        except Exception:  # noqa: BLE001 - never block adding an item on a lookup
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
        # Paprika hasn't learned this ingredient; guess from keywords.
        guessed = guess_aisle_name(key, set(aisle_names.values()))
        if guessed:
            uid = next(u for u, n in aisle_names.items() if n == guessed)
            return guessed, uid
        return "", ""
