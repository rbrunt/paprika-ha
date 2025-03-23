"""The Paprika integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .paprika_api import PaprikaApi

# T List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
_PLATFORMS: list[Platform] = [Platform.CALENDAR]

# TODO Create ConfigEntry type alias with API object
# TODO Rename type alias and update all entry annotations


class PaprikaApiConfig:
    token: str
    api_client: PaprikaApi


type PaprikaConfigEntry = ConfigEntry[PaprikaApiConfig]  # noqa: F821


# DONE Update entry annotation
async def async_setup_entry(hass: HomeAssistant, entry: PaprikaConfigEntry) -> bool:
    """Set up Paprika from a config entry."""

    client = PaprikaApi(entry.token)
    entry.api_client = client

    # TODO 1. Create API instance
    # TODO 2. Validate the API connection (and authentication)
    # TODO 3. Store an API object for your platforms to access
    # entry.runtime_data = MyAPI(...)

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PaprikaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
