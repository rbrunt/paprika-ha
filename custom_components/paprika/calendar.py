import logging
from typing import TYPE_CHECKING
from homeassistant.components.calendar import CalendarEntity, CalendarEvent

from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt
from datetime import datetime, timedelta


from .api import MealType, PlannedMeal

if TYPE_CHECKING:
    from .coordinator import PaprikaCoordinator
    from .data import PaprikaConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


LOGGER = logging.getLogger(__name__)


class PaprikaMealCalendar(CalendarEntity, CoordinatorEntity["PaprikaCoordinator"]):
    def __init__(self, coordinator: "PaprikaCoordinator", meal_type: MealType):
        super().__init__(coordinator)
        self.meal_type = meal_type
        # self.entity_description = f"Calendar for {meal_type.name}"
        self._attr_has_entity_name = False

    @property
    def name(self):
        """Name of the entity."""
        return f"Paprika {self.meal_type.name}"

    @property
    def event(self):
        LOGGER.info("@@@ Getting event")

        if not self.coordinator.data.meals and len(self.coordinator.data.meals) > 0:
            return None

        def filter_by_type(m: PlannedMeal) -> bool:
            return m["type"] == self.meal_type

        meals = filter(filter_by_type, self.coordinator.data.meals)
        today = homeassistant.util.dt.now().date()
        meal = list(filter(lambda x: x["date"] == today, meals))
        LOGGER.info(meals)
        LOGGER.info(meal)
        if len(meal) >= 1:
            return CalendarEvent(
                start=meal[0]["date"],
                end=meal[0]["date"] + timedelta(days=1),
                summary=meal[0]["name"],
                description=meal[0]["name"],
            )
        else:
            return None

    async def async_get_events(self, hass, start_date, end_date):
        LOGGER.info("@@@ Getting events")
        LOGGER.info(start_date)
        LOGGER.info(end_date)

        def filter_by_type(m: PlannedMeal) -> bool:
            return m["type"] == self.meal_type

        def filter_between_dates(m: PlannedMeal) -> bool:
            return start_date.date() <= m["date"] < end_date.date()

        meals = filter(filter_by_type, self.coordinator.data.meals)
        meals_in_range = filter(filter_between_dates, meals)

        return [
            CalendarEvent(
                start=m["date"],
                end=m["date"] + timedelta(days=1),
                summary=m["name"],
                description=m["name"],
            )
            for m in meals_in_range
        ]


async def async_setup_entry(
    hass: "HomeAssistant",  # noqa: ARG001 Unused function argument: `hass`
    entry: "PaprikaConfigEntry",
    async_add_entities: "AddEntitiesCallback",
) -> None:
    """Set up the sensor platform."""
    async_add_entities(
        [
            PaprikaMealCalendar(
                coordinator=entry.runtime_data.coordinator, meal_type=MealType.Dinner
            ),
            PaprikaMealCalendar(
                coordinator=entry.runtime_data.coordinator, meal_type=MealType.Lunch
            ),
            PaprikaMealCalendar(
                coordinator=entry.runtime_data.coordinator, meal_type=MealType.Breakfast
            ),
            PaprikaMealCalendar(
                coordinator=entry.runtime_data.coordinator, meal_type=MealType.Snack
            ),
        ]
    )
