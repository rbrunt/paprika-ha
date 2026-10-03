from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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
