import logging
from typing import TYPE_CHECKING

from homeassistant.components.todo import TodoItem, TodoListEntity
from homeassistant.components.todo.const import TodoItemStatus
from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import PaprikaCoordinator
    from .data import PaprikaConfigEntry

LOGGER = logging.getLogger(__name__)


class PaprikaGroceryList(TodoListEntity, CoordinatorEntity["PaprikaCoordinator"]):
    def __init__(
        self,
        coordinator: "PaprikaCoordinator",
        entry: "PaprikaConfigEntry",
    ):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.title}_groceries_list"
        self._attr_has_entity_name = False

    @property
    def name(self) -> str:
        return "Paprika Grocery List"

    @property
    def todo_items(self) -> list[TodoItem] | None:
        if not self.coordinator.data.groceries:
            return None
        return [
            TodoItem(
                uid=item["uid"],
                summary=item["name"],
                status=TodoItemStatus.COMPLETED
                if item["purchased"]
                else TodoItemStatus.NEEDS_ACTION,
            )
            for item in sorted(
                self.coordinator.data.groceries, key=lambda i: i["order_flag"]
            )
        ]


async def async_setup_entry(
    hass: "HomeAssistant",  # noqa: ARG001 Unused function argument: `hass`
    entry: "PaprikaConfigEntry",
    async_add_entities: "AddEntitiesCallback",
) -> None:
    """Set up the sensor platform."""
    async_add_entities(
        [
            # TODO: split by list name?
            PaprikaGroceryList(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
            ),
        ]
    )
