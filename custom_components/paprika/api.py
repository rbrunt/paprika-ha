import logging
from datetime import date, datetime
from enum import Enum
from typing import NewType, Optional, TypedDict, cast

import aiohttp

_LOGGER = logging.getLogger(__name__)

START_DATE_FILTER = date(
    2025, 1, 1
)  # Only process meals after this date (see issue #13)

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
    scale: Optional[int]
    is_ingredient: bool


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


class PaprikaAuthenticationError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class PaprikaApi:
    def __del__(self):
        # TODO: verify this works as expected when erroring during setup.
        self.session.close()

    def __init__(self, token: str):
        _LOGGER.info("Setting up client")
        self.access_token = token
        self.session = aiohttp.ClientSession("https://www.paprikaapp.com/api/v2/")
        self.session.headers["authorization"] = f"Bearer {self.access_token}"

    @classmethod
    async def login(cls, email: str, password: str):
        """Use a username and password to get a token that can be used to initialise the client for other calls."""
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                "https://paprikaapp.com/api/v1/account/login",
                data={"email": email, "password": password},
            )
            json_response = await response.json()

            if json_response.get("error"):
                _LOGGER.error(
                    f"Error from authentication endpoint: {json_response['error']['message']}"
                )
                raise PaprikaAuthenticationError(json_response["error"]["message"])

            return json_response["result"]["token"]

    async def get_meal_types(self) -> list[MealType]:
        response = await self.session.get("sync/mealtypes")
        response.raise_for_status()
        response_json = await response.json()
        return [cast("MealType", item) for item in response_json["result"]]

    async def get_status(self) -> SyncStatus:
        """Get the sync status to check if any data has changed."""
        response = await self.session.get("sync/status")
        response.raise_for_status()
        response_json = await response.json()
        return cast("SyncStatus", response_json["result"])

    async def get_meals(self, meal_types: list[MealType]) -> list[PlannedMeal]:
        meal_types_by_id = {mt["uid"]: mt for mt in meal_types}
        response = await self.session.get("sync/meals")
        response.raise_for_status()
        response_json = await response.json()
        meals: list[PlannedMeal] = []
        for meal in response_json["result"]:
            meal_date = datetime.strptime(meal["date"][:10], "%Y-%m-%d").date()
            # Skip meals before START_DATE_FILTER to avoid processing old data with bad ids (see issue #13)
            if meal_date < START_DATE_FILTER:
                _LOGGER.debug("Skipping meal with date before cutoff: %s", meal)
                continue
            meal["date"] = meal_date
            meal["type"] = meal_types_by_id[meal["type_uid"]]
            meals.append(cast("PlannedMeal", meal))
        _LOGGER.debug("Got %s meals from API", len(meals))
        return meals

    async def get_groceries(self) -> list[GroceryListItem]:
        """Get grocery list items, for all lists."""
        response = await self.session.get("sync/groceries")
        response.raise_for_status()
        response_json = await response.json()
        return [cast("GroceryListItem", item) for item in response_json["result"]]
