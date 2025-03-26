from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .api import PaprikaApi
    from .coordinator import PaprikaCoordinator


class PaprikaApiConfig:
    token: str


type PaprikaConfigEntry = ConfigEntry[PaprikaApiConfig]  # noqa: F821


@dataclass
class PaprikaRuntimeData:
    client: "PaprikaApi"
    coordinator: "PaprikaCoordinator"
