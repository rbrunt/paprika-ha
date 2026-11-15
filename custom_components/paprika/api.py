import gzip
import io
import json
import logging
import uuid
from datetime import date
from enum import Enum
from collections.abc import Awaitable, Callable
from typing import Any, NewType, Optional, TypedDict, cast

import aiohttp

_LOGGER = logging.getLogger(__name__)

START_DATE_FILTER = date(2025, 1, 1)  # Only process meals after this date (see issue #13)

MealId = NewType("MealId", str)
RecipeID = NewType("RecipeID", str)


class SyncStatus(TypedDict):
    categories: int
    recipes: int
    photos: int
    groceries: int
    grocerylists: int
    groceryaisles: int
    groceryingredients: int
    meals: int
    mealtypes: int
    bookmarks: int
    pantry: int
    pantrylocations: int
    menus: int
    menuitems: int


class MealType(TypedDict):
    uid: str
    name: str
    order_flag: int
    color: str
    export_all_day: bool
    export_time: int
    original_type: int


class PlannedMeal(TypedDict):
    uid: MealId
    recipe_uid: RecipeID
    date: date
    type: MealType
    name: str
    order_flag: int
    type_uid: str
    scale: int | None
    is_ingredient: bool


class Recipe(TypedDict):
    uid: RecipeID
    hash: str
    name: str
    ingredients: str
    directions: str
    notes: str
    servings: str
    prep_time: str
    cook_time: str
    total_time: str
    source: str
    source_url: str


class GroceryList(TypedDict):
    uid: str
    name: str
    order_flag: int
    is_default: bool
    reminders_list: str


class GroceryListItem(TypedDict):
    uid: str
    recipe_uid: RecipeID | None
    name: str
    order_flag: int
    purchased: bool
    aisle: str
    ingredient: str
    recipe: str
    instruction: str
    quantity: str
    separate: bool
    aisle_uid: str
    list_uid: str


class GroceryAisle(TypedDict):
    uid: str
    name: str
    order_flag: int


class GroceryIngredient(TypedDict):
    uid: str
    name: str
    aisle_uid: str | None


class PaprikaAuthenticationError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class PaprikaApi:
    async def async_close(self):
        await self.session.close()

    def __init__(self, token: str):
        _LOGGER.info("Setting up client")
        self.access_token = token
        self.session = aiohttp.ClientSession("https://www.paprikaapp.com/api/v2/")
        self.session.headers["authorization"] = f"Bearer {self.access_token}"
        self._recipe_cache: dict[RecipeID, Recipe] = {}
        # The last sync/status read, and each list endpoint's last result with the
        # status counter it was read at. See _cached.
        self._status: SyncStatus | None = None
        self._cache: dict[str, tuple[int, Any]] = {}

    @classmethod
    async def login(cls, email: str, password: str) -> str:
        """Use a username and password to get a token that can be used to initialise the client for other calls."""
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                "https://paprikaapp.com/api/v1/account/login",
                data={"email": email, "password": password},
            )
            json_response = await response.json()

            if json_response.get("error"):
                _LOGGER.error(
                    "Error from authentication endpoint: %s", json_response["error"]["message"]
                )
                raise PaprikaAuthenticationError(json_response["error"]["message"])

            return json_response["result"]["token"]

    async def refresh_status(self) -> SyncStatus:
        """Read sync/status, so the get_* methods refetch only entities that changed."""
        self._status = await self.get_status()
        return self._status

    async def _cached[T](self, entity: str, fetch: Callable[[], Awaitable[T]]) -> T:
        """Return the last result for `entity` if its status counter hasn't moved.

        Each sync/status counter is a revision number for one entity, and moves when
        that entity changes (see tests/fixtures/README.md). A result is stored only
        after a successful fetch, so a failed one is retried on the next call. Before
        the first refresh_status, nothing is cached.
        """
        counter = self._status.get(entity) if self._status else None
        if counter is None:
            return await fetch()
        hit = self._cache.get(entity)
        if hit and hit[0] == counter:
            return hit[1]
        value = await fetch()
        self._cache[entity] = (counter, value)
        return value

    async def _get_list(self, entity: str) -> list[dict]:
        response = await self.session.get(f"sync/{entity}")
        response.raise_for_status()
        response_json = await response.json()
        return response_json["result"]

    async def _get_cached_list(self, entity: str) -> list[Any]:
        return await self._cached(entity, lambda: self._get_list(entity))

    async def get_meal_types(self) -> list[MealType]:
        return await self._get_cached_list("mealtypes")

    async def get_status(self) -> SyncStatus:
        """Get the sync status to check if any data has changed."""
        response = await self.session.get("sync/status")
        response.raise_for_status()
        response_json = await response.json()
        return cast("SyncStatus", response_json["result"])

    async def get_meals(self, meal_types: list[MealType]) -> list[PlannedMeal]:
        """Get planned meals, each with its meal type attached.

        The raw meals are cached, and the meal types attached on every call, so a
        change to the meal types alone doesn't refetch meals.
        """
        meal_types_by_id = {mt["uid"]: mt for mt in meal_types}
        meals: list[PlannedMeal] = []
        for meal in await self._get_cached_list("meals"):
            meal_date = date.fromisoformat(meal["date"][:10])
            # Skip meals before START_DATE_FILTER to avoid processing old data with bad ids (see issue #13)
            if meal_date < START_DATE_FILTER:
                _LOGGER.debug("Skipping meal with date before cutoff: %s", meal)
                continue
            # Meals from before Paprika changed its meal type IDs can have a null or
            # unknown type_uid even when dated after START_DATE_FILTER.
            meal_type = meal_types_by_id.get(meal.get("type_uid"))
            if meal_type is None:
                _LOGGER.warning(
                    "Skipping meal with unknown meal type (type_uid=%r): %s",
                    meal.get("type_uid"),
                    meal,
                )
                continue
            meals.append(cast("PlannedMeal", {**meal, "date": meal_date, "type": meal_type}))
        _LOGGER.debug("Got %s meals from API", len(meals))
        return meals

    async def get_recipe_hashes(self) -> dict[RecipeID, str]:
        """Get the hash of every recipe, to tell which ones changed."""
        return {item["uid"]: item["hash"] for item in await self._get_cached_list("recipes")}

    async def get_recipe(self, uid: RecipeID) -> Recipe:
        response = await self.session.get(f"sync/recipe/{uid}")
        response.raise_for_status()
        response_json = await response.json()
        return cast("Recipe", response_json["result"])

    async def get_recipes(self, uids: set[RecipeID]) -> tuple[dict[RecipeID, Recipe], bool]:
        """Get several recipes, re-fetching only those that are new or changed.

        Unlike the other sync endpoints, recipes come one request per recipe, so
        recipes are cached by the hash Paprika lists for each one. A recipe that
        fails to fetch or times out falls back to its cached copy, if there is
        one. Recipes no longer asked for are dropped from the cache.

        Returns the recipes and whether every one was fetched successfully, so
        the caller can retry later if any were missed.
        """
        hashes = await self.get_recipe_hashes()
        recipes: dict[RecipeID, Recipe] = {}
        complete = True
        for uid in uids:
            if uid not in hashes:
                # A planned meal can point at a recipe that was deleted.
                continue
            cached = self._recipe_cache.get(uid)
            if cached and cached.get("hash") == hashes[uid]:
                recipes[uid] = cached
                continue
            try:
                recipes[uid] = await self.get_recipe(uid)
            except (aiohttp.ClientError, TimeoutError) as err:
                _LOGGER.warning("Could not fetch recipe %s: %s", uid, err)
                complete = False
                if cached:
                    recipes[uid] = cached
        self._recipe_cache = recipes
        return recipes, complete

    async def get_groceries(self) -> list[GroceryListItem]:
        """Get grocery list items, for all lists."""
        return await self._get_cached_list("groceries")

    async def get_grocery_lists(self) -> list[GroceryList]:
        return await self._get_cached_list("grocerylists")

    async def get_grocery_aisles(self) -> list[GroceryAisle]:
        return await self._get_cached_list("groceryaisles")

    async def get_grocery_ingredients(self) -> list[GroceryIngredient]:
        """Get Paprika's ingredient name to aisle mapping."""
        return await self._get_cached_list("groceryingredients")

    async def _post_sync(self, entity: str, payload: list | dict) -> None:
        json_bytes = json.dumps(payload).encode("utf-8")
        compressed = io.BytesIO()
        with gzip.GzipFile(fileobj=compressed, mode="wb") as gz:
            gz.write(json_bytes)
        compressed.seek(0)

        boundary = str(uuid.uuid4())
        body = (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=data; filename=file; filename*=utf-8''file\r\n"
            f"\r\n"
        ).encode()
        body += compressed.read()
        body += f"\r\n--{boundary}--\r\n".encode()

        response = await self.session.post(
            f"sync/{entity}/",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        response.raise_for_status()

    async def save_grocery_items(self, items: list[GroceryListItem]) -> None:
        # The server bumps the groceries counter for this anyway, but drop the cache
        # so a read before the next refresh_status doesn't miss the change.
        self._cache.pop("groceries", None)
        await self._post_sync("groceries", items)
