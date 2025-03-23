


from typing import Any
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import PaprikaConfigEntry


class PaprikaCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    config_entry: PaprikaConfigEntry

    async def _async_update_data(self) -> Any:
        """Update data via library."""
        self.meals = await self.config_entry.runtime_data.client.get_meals()
        