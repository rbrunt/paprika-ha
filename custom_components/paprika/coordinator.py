from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from .api import GroceryListItem, MealType, PlannedMeal, SyncStatus
    from .data import PaprikaConfigEntry


@dataclass
class PaprikaData:
    status: "SyncStatus"
    meals: list["PlannedMeal"]
    groceries: list["GroceryListItem"]
    meal_types: list["MealType"]


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
        return PaprikaData(
            status=current_status,
            meal_types=meal_types,
            meals=meals,
            groceries=groceries,
        )
