from enum import Enum
import json
import logging
from typing import NewType, Optional, TypedDict, cast
from datetime import date, datetime
import aiohttp

_LOGGER = logging.getLogger(__name__)


MealId = NewType("MealId", str)
RecipeID = NewType("RecipeID", str)


class MealType(Enum):
    Breakfast = 0
    Lunch = 1
    Dinner = 2
    Snack = 3


class PlannedMeal(TypedDict):
    uid: MealId
    recipe_uid: RecipeID
    date: date
    type: MealType
    name: str
    order_flag: int
    type_uid: str  # TODO
    scale: Optional[int]
    is_ingredient: bool


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
            # TODO: remove this once confirmed working:
            _LOGGER.warning(json.dumps(json_response))
            return json_response["result"]["token"]

    async def get_meals(self):
        response = await self.session.get("sync/meals")
        response.raise_for_status()
        response_json = await response.json()
        meals: list[PlannedMeal] = []
        for meal in response_json["result"]:
            meal["date"] = datetime.strptime(meal["date"][:10], "%Y-%m-%d").date()
            meal["type"] = MealType(meal["type"])
            meals.append(cast(PlannedMeal, meal))
        return meals
