from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from .api import GroceryListItem, MealType, PlannedMeal
    from .data import PaprikaConfigEntry


@dataclass
class PaprikaData:
    meals: list["PlannedMeal"]
    groceries: list["GroceryListItem"]
    meal_types: list["MealType"]


class PaprikaCoordinator(DataUpdateCoordinator[PaprikaData]):
    """Class to manage fetching data from the API."""

    config_entry: "PaprikaConfigEntry"

    async def _async_update_data(self) -> Any:
        """Update data via library."""
        meal_types = await self.config_entry.runtime_data.client.get_meal_types()
        meals = await self.config_entry.runtime_data.client.get_meals(meal_types)
        groceries = await self.config_entry.runtime_data.client.get_groceries()
        return PaprikaData(meal_types=meal_types, meals=meals, groceries=groceries)
