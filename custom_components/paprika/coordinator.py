


from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from .data import PaprikaConfigEntry, PlannedMeal

@dataclass
class PaprikaData:
    meals: list['PlannedMeal']
    recipe_count: int


class PaprikaCoordinator(DataUpdateCoordinator[PaprikaData]):
    """Class to manage fetching data from the API."""

    config_entry: 'PaprikaConfigEntry'

    async def _async_update_data(self) -> Any:
        """Update data via library."""
        meals = await self.config_entry.runtime_data.client.get_meals()
        recipe_count = await self.config_entry.runtime_data.client.get_recipe_count()
        data = PaprikaData(meals = meals, recipe_count= recipe_count)
        return data
        