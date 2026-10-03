import logging
import uuid
from typing import TYPE_CHECKING

from homeassistant.components.todo import TodoItem, TodoListEntity, TodoListEntityFeature
from homeassistant.components.todo.const import TodoItemStatus
from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .api import GroceryList
    from .coordinator import PaprikaCoordinator
    from .data import PaprikaConfigEntry

LOGGER = logging.getLogger(__name__)


class PaprikaGroceryList(TodoListEntity, CoordinatorEntity["PaprikaCoordinator"]):
    def __init__(
        self,
        coordinator: "PaprikaCoordinator",
        entry: "PaprikaConfigEntry",
        grocery_list: "GroceryList",
    ):
        super().__init__(coordinator)
        self.grocery_list = grocery_list
        self._attr_unique_id = f"{entry.title}_groceries_list_{grocery_list['uid']}"
        self._attr_has_entity_name = False
        self._attr_supported_features = (
            TodoListEntityFeature.CREATE_TODO_ITEM
            | TodoListEntityFeature.UPDATE_TODO_ITEM
            | TodoListEntityFeature.DELETE_TODO_ITEM
            | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
        )

    @property
    def name(self) -> str:
        return f"Paprika {self.grocery_list['name']}"

    @property
    def todo_items(self) -> list[TodoItem] | None:
        if not self.coordinator.data.groceries:
            return None
        filtered = [
            item
            for item in self.coordinator.data.groceries
            if item["list_uid"] == self.grocery_list["uid"]
        ]
        return [
            TodoItem(
                uid=item["uid"],
                summary=item["name"],
                description=item["quantity"] or None,
                status=TodoItemStatus.COMPLETED
                if item["purchased"]
                else TodoItemStatus.NEEDS_ACTION,
            )
            for item in sorted(filtered, key=lambda i: i["order_flag"])
        ]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        new_item = {
            "uid": str(uuid.uuid4()).upper(),
            "recipe_uid": None,
            "name": item.summary,
            "order_flag": 0,
            "purchased": False,
            "aisle": "",
            "ingredient": item.summary.lower(),
            "recipe": None,
            "instruction": "",
            "quantity": item.description or "",
            "separate": False,
            "aisle_uid": "",
            "list_uid": self.grocery_list["uid"],
        }
        await self.coordinator.async_save_grocery_items([new_item])

    async def async_update_todo_item(self, item: TodoItem) -> None:
        existing = next(
            (g for g in self.coordinator.data.groceries if g["uid"] == item.uid),
            None,
        )
        if not existing:
            return
        updated = existing.copy()
        updated["name"] = item.summary
        updated["quantity"] = item.description or ""
        updated["purchased"] = item.status == TodoItemStatus.COMPLETED
        await self.coordinator.async_save_grocery_items([updated])

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        items_to_update = []
        for uid in uids:
            existing = next(
                (g for g in self.coordinator.data.groceries if g["uid"] == uid),
                None,
            )
            if existing:
                updated = existing.copy()
                updated["purchased"] = True
                items_to_update.append(updated)
        if items_to_update:
            await self.coordinator.async_save_grocery_items(items_to_update)


async def async_setup_entry(
    hass: "HomeAssistant",  # noqa: ARG001 Unused function argument: `hass`
    entry: "PaprikaConfigEntry",
    async_add_entities: "AddEntitiesCallback",
) -> None:
    """Set up the sensor platform."""
    async_add_entities(
        [
            PaprikaGroceryList(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                grocery_list=gl,
            )
            for gl in entry.runtime_data.coordinator.data.grocery_lists
        ]
    )
