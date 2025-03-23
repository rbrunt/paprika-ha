"""The Paprika integration."""

from __future__ import annotations
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .paprika_api import PaprikaApi

# List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
_PLATFORMS: list[Platform] = [Platform.CALENDAR]


class PaprikaApiConfig:
    token: str


type PaprikaConfigEntry = ConfigEntry[PaprikaApiConfig]  # noqa: F821

@dataclass
class PaprikaRuntimeData:
    client: PaprikaApi


# DONE Update entry annotation
async def async_setup_entry(hass: HomeAssistant, entry: PaprikaConfigEntry) -> bool:
    """Set up Paprika from a config entry."""



    token = entry.data["token"]
    client = PaprikaApi(token)
    entry.runtime_data = PaprikaRuntimeData(client=client)

    # TODO 1. Create API instance
    # TODO 2. Validate the API connection (and authentication)
    # TODO 3. Store an API object for your platforms to access
    # entry.runtime_data = MyAPI(...)

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PaprikaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
