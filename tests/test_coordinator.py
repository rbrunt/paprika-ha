"""Tests for PaprikaCoordinator's polling, run through Home Assistant."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.todo import DOMAIN as TODO_DOMAIN
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.paprika.const import CONF_RECIPE_FORMAT, DOMAIN, RECIPE_FORMAT_HTML

from .fake_paprika import EMAIL, TOKEN, FakePaprika

TODO_ENTITY = "todo.paprika_groceries"
POLL = timedelta(minutes=15, seconds=1)

# The day the fixtures were captured. The coordinator only fetches recipes for meals
# planned recently, so without a fixed date those tests would stop fetching any.
CAPTURE_DATE = "2026-11-15 12:00:00"


@pytest.fixture(autouse=True)
def _frozen_at_capture_date(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    freezer.move_to(CAPTURE_DATE)
    return freezer


async def _set_up(hass: HomeAssistant, options: dict | None = None) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, title=EMAIL, data={"token": TOKEN}, options=options or {}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(POLL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _open_items(paprika: FakePaprika) -> int:
    return sum(not g["purchased"] for g in paprika.data["groceries"])


def _recipe_fetches(paprika: FakePaprika) -> list[str]:
    return [p for p in paprika.paths() if p.startswith("sync/recipe/")]


async def test_quiet_poll_requests_only_status(
    hass: HomeAssistant, paprika: FakePaprika, freezer: FrozenDateTimeFactory
) -> None:
    await _set_up(hass)
    paprika.requests.clear()

    await _poll(hass, freezer)

    assert paprika.paths() == ["sync/status"]


async def test_quiet_poll_with_recipe_details_requests_only_status(
    hass: HomeAssistant, paprika: FakePaprika, freezer: FrozenDateTimeFactory
) -> None:
    await _set_up(hass, {CONF_RECIPE_FORMAT: RECIPE_FORMAT_HTML})
    assert _recipe_fetches(paprika), "setup should fetch recipes for recently planned meals"
    paprika.requests.clear()

    await _poll(hass, freezer)

    assert paprika.paths() == ["sync/status"]


async def test_grocery_change_refetches_only_groceries(
    hass: HomeAssistant, paprika: FakePaprika, freezer: FrozenDateTimeFactory
) -> None:
    await _set_up(hass)
    paprika.requests.clear()
    item = next(g for g in paprika.data["groceries"] if not g["purchased"])
    paprika.edit("groceries", lambda _: item.update(purchased=True))

    await _poll(hass, freezer)

    assert paprika.paths() == ["sync/status", "sync/groceries"]
    assert hass.states.get(TODO_ENTITY).state == str(_open_items(paprika))


async def test_failed_poll_is_retried_on_next_poll(
    hass: HomeAssistant, paprika: FakePaprika, freezer: FrozenDateTimeFactory
) -> None:
    await _set_up(hass)
    paprika.edit("groceries", lambda items: items.pop())
    paprika.fail("sync/groceries", 500)
    await _poll(hass, freezer)
    paprika.recover("sync/groceries")
    paprika.requests.clear()

    await _poll(hass, freezer)

    assert paprika.paths() == ["sync/status", "sync/groceries"]
    assert hass.states.get(TODO_ENTITY).state == str(_open_items(paprika))


async def test_todo_update_is_shown_at_once_and_next_poll_reads_server(
    hass: HomeAssistant, paprika: FakePaprika, freezer: FrozenDateTimeFactory
) -> None:
    await _set_up(hass)
    item = next(g for g in paprika.data["groceries"] if not g["purchased"])
    before = int(hass.states.get(TODO_ENTITY).state)

    await hass.services.async_call(
        TODO_DOMAIN,
        "update_item",
        {"item": item["uid"], "status": "completed"},
        target={"entity_id": TODO_ENTITY},
        blocking=True,
    )

    assert paprika.paths("POST") == ["sync/groceries"]
    assert hass.states.get(TODO_ENTITY).state == str(before - 1)

    # Someone unticks the item in the app before the next poll.
    paprika.edit(
        "groceries",
        lambda items: next(g for g in items if g["uid"] == item["uid"]).update(purchased=False),
    )
    paprika.requests.clear()

    await _poll(hass, freezer)

    assert paprika.paths() == ["sync/status", "sync/groceries"]
    assert hass.states.get(TODO_ENTITY).state == str(before)


async def _add_item(hass: HomeAssistant, name: str) -> None:
    await hass.services.async_call(
        TODO_DOMAIN,
        "add_item",
        {"item": name},
        target={"entity_id": TODO_ENTITY},
        blocking=True,
    )


async def test_adding_item_reads_aisle_mapping_once_until_it_changes(
    hass: HomeAssistant, paprika: FakePaprika
) -> None:
    await _set_up(hass)
    paprika.requests.clear()

    await _add_item(hass, "first")
    await _add_item(hass, "second")

    assert paprika.paths() == [
        "sync/status",
        "sync/groceryingredients",
        "sync/groceryaisles",
        "sync/status",
    ]
    assert paprika.paths("POST") == ["sync/groceries", "sync/groceries"]

    # Paprika learns a new ingredient's aisle, e.g. from an edit in the app.
    aisle = paprika.data["groceryaisles"][0]
    paprika.edit(
        "groceryingredients",
        lambda items: items.append(
            {"uid": "NEW-INGREDIENT", "name": "kohlrabi", "aisle_uid": aisle["uid"]}
        ),
    )
    paprika.requests.clear()

    await _add_item(hass, "kohlrabi")

    assert paprika.paths() == ["sync/status", "sync/groceryingredients"]
    added = next(g for g in paprika.data["groceries"] if g["name"] == "kohlrabi")
    assert (added["aisle"], added["aisle_uid"]) == (aisle["name"], aisle["uid"])
