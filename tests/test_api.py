"""Tests for PaprikaApi, run against the fake Paprika account."""

from datetime import date
import uuid

import aiohttp
import pytest

from custom_components.paprika.api import (
    START_DATE_FILTER,
    PaprikaApi,
    PaprikaAuthenticationError,
)

from .fake_paprika import EMAIL, PASSWORD, TOKEN, FakePaprika


async def test_requests_outside_paprika_are_refused(client: PaprikaApi) -> None:
    async with aiohttp.ClientSession() as session:
        with pytest.raises(aiohttp.ClientConnectionError, match="non-Paprika URL"):
            await session.get("https://example.com/")


async def test_login_returns_token() -> None:
    assert await PaprikaApi.login(EMAIL, PASSWORD) == TOKEN


async def test_login_with_wrong_password_raises() -> None:
    with pytest.raises(PaprikaAuthenticationError):
        await PaprikaApi.login(EMAIL, "wrong")


async def test_get_status_returns_counters(client: PaprikaApi, paprika: FakePaprika) -> None:
    status = await client.get_status()

    assert status == paprika.status
    assert paprika.paths() == ["sync/status"]


async def test_http_error_raises(client: PaprikaApi, paprika: FakePaprika) -> None:
    paprika.fail("sync/groceries", 500)

    with pytest.raises(aiohttp.ClientResponseError):
        await client.get_groceries()


async def test_get_meals_parses_date_and_attaches_meal_type(client: PaprikaApi) -> None:
    meal_types = await client.get_meal_types()
    meals = await client.get_meals(meal_types)

    assert meals
    by_uid = {t["uid"]: t for t in meal_types}
    for meal in meals:
        assert isinstance(meal["date"], date)
        assert meal["type"] == by_uid[meal["type_uid"]]


async def test_get_meals_skips_meals_before_cutoff(
    client: PaprikaApi, paprika: FakePaprika
) -> None:
    old = [m["uid"] for m in paprika.data["meals"] if m["date"] < str(START_DATE_FILTER)]
    assert old, "fixture should include meals from before the cutoff"

    meals = await client.get_meals(await client.get_meal_types())

    assert not {m["uid"] for m in meals} & set(old)
    assert all(m["date"] >= START_DATE_FILTER for m in meals)


@pytest.mark.parametrize("type_uid", [None, "UNKNOWN-TYPE"])
async def test_get_meals_skips_meal_with_unknown_type(
    client: PaprikaApi, paprika: FakePaprika, type_uid: str | None
) -> None:
    """Regression test for #81: one bad meal must not break the rest."""
    bad = paprika.data["meals"][-1]
    bad["type_uid"] = type_uid

    meals = await client.get_meals(await client.get_meal_types())

    uids = {m["uid"] for m in meals}
    assert bad["uid"] not in uids
    assert len(uids) > 0


async def test_save_grocery_items_posts_gzipped_payload(
    client: PaprikaApi, paprika: FakePaprika
) -> None:
    list_uid = paprika.data["grocerylists"][0]["uid"]
    item = {
        "uid": str(uuid.uuid4()).upper(),
        "recipe_uid": None,
        "name": "test item",
        "order_flag": 0,
        "purchased": False,
        "aisle": "",
        "ingredient": "test item",
        "recipe": "",
        "instruction": "",
        "quantity": "",
        "separate": False,
        "aisle_uid": "",
        "list_uid": list_uid,
    }
    before = paprika.status["groceries"]

    await client.save_grocery_items([item])

    assert paprika.paths("POST") == ["sync/groceries"]
    assert paprika.posted["groceries"] == [[item]]
    assert item in await client.get_groceries()
    assert paprika.status["groceries"] == before + 1


async def test_save_grocery_items_with_deleted_flag_removes_item(
    client: PaprikaApi, paprika: FakePaprika
) -> None:
    item = (await client.get_groceries())[0]

    await client.save_grocery_items([{**item, "deleted": True}])

    assert item["uid"] not in {g["uid"] for g in await client.get_groceries()}


async def test_get_recipes_fetches_each_recipe_once_until_it_changes(
    client: PaprikaApi, paprika: FakePaprika
) -> None:
    uids = set(paprika.recipes)

    recipes, complete = await client.get_recipes(uids)
    assert complete
    assert set(recipes) == uids
    assert len([p for p in paprika.paths() if p.startswith("sync/recipe/")]) == len(uids)

    paprika.requests.clear()
    _, complete = await client.get_recipes(uids)
    assert complete
    assert paprika.paths() == ["sync/recipes"]

    edited = next(iter(uids))
    paprika.edit_recipe(edited, name="Renamed")
    paprika.requests.clear()
    recipes, _ = await client.get_recipes(uids)
    assert paprika.paths() == ["sync/recipes", f"sync/recipe/{edited}"]
    assert recipes[edited]["name"] == "Renamed"


@pytest.mark.parametrize("error", [500, TimeoutError()])
async def test_get_recipes_keeps_cached_copy_when_refetch_fails(
    client: PaprikaApi, paprika: FakePaprika, error: int | BaseException
) -> None:
    uid = next(iter(paprika.recipes))
    first, _ = await client.get_recipes({uid})
    paprika.edit_recipe(uid, name="Renamed")
    paprika.fail(f"sync/recipe/{uid}", error)

    recipes, complete = await client.get_recipes({uid})

    assert not complete
    assert recipes[uid] == first[uid]


async def test_get_recipes_skips_recipe_missing_from_account(
    client: PaprikaApi, paprika: FakePaprika
) -> None:
    recipes, complete = await client.get_recipes({"DELETED-RECIPE"})

    assert recipes == {}
    assert complete
    assert paprika.paths() == ["sync/recipes"]
