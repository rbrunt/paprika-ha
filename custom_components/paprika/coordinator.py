from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from .data import PaprikaConfigEntry, PlannedMeal


@dataclass
class PaprikaData:
    meals: list["PlannedMeal"]


class PaprikaCoordinator(DataUpdateCoordinator[PaprikaData]):
    """Class to manage fetching data from the API."""

    config_entry: "PaprikaConfigEntry"

    async def _async_update_data(self) -> Any:
        """Update data via library."""
        meals = await self.config_entry.runtime_data.client.get_meals()
        data = PaprikaData(meals=meals)
        return data
