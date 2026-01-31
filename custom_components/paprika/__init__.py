"""The Paprika integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import PaprikaApi
from .const import DOMAIN
from .coordinator import PaprikaCoordinator
from .data import PaprikaConfigEntry, PaprikaRuntimeData

_PLATFORMS: list[Platform] = [Platform.CALENDAR, Platform.TODO]


LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: PaprikaConfigEntry) -> bool:
    """Set up Paprika from a config entry."""

    coordinator = PaprikaCoordinator(
        hass=hass,
        logger=LOGGER,
        name=DOMAIN,
        update_interval=timedelta(minutes=15),
    )

    token = entry.data["token"]
    client = PaprikaApi(token)
    entry.runtime_data = PaprikaRuntimeData(client=client, coordinator=coordinator)

    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    # entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PaprikaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
