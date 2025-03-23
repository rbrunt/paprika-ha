type PaprikaConfigEntry = ConfigEntry[PaprikaApiConfig]  # noqa: F821

@dataclass
class PaprikaRuntimeData:
    client: PaprikaApi
    coordinator: PaprikaCoordinator
