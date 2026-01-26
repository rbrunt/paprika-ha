import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import homeassistant.util.dt
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import MealType, PlannedMeal

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import PaprikaCoordinator
    from .data import PaprikaConfigEntry


LOGGER = logging.getLogger(__name__)


class PaprikaMealCalendar(CalendarEntity, CoordinatorEntity["PaprikaCoordinator"]):
    def __init__(
        self,
        coordinator: "PaprikaCoordinator",
        entry: "PaprikaConfigEntry",
        meal_type: MealType,
    ):
        super().__init__(coordinator)
        self.meal_type = meal_type
        self._attr_unique_id = f"{entry.title}_calendar_{self.meal_type['name']}"
        self._attr_has_entity_name = False

    @property
    def name(self):
        """Name of the entity."""
        return f"Paprika {self.meal_type['name']}"

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


class PaprikaAllMealsCalendar(CalendarEntity, CoordinatorEntity["PaprikaCoordinator"]):
    def __init__(
        self,
        coordinator: "PaprikaCoordinator",
        entry: "PaprikaConfigEntry",
    ):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.title}_calendar_all_meals"
        self._attr_has_entity_name = False

    @property
    def name(self):
        """Name of the entity."""
        return "Paprika All Meals"

    @property
    def event(self):
        LOGGER.info("@@@ Getting event for all meals")

        if not self.coordinator.data.meals and len(self.coordinator.data.meals) > 0:
            return None

        today = homeassistant.util.dt.now().date()
        meals_today = [m for m in self.coordinator.data.meals if m["date"] == today]

        LOGGER.info(meals_today)

        if len(meals_today) >= 1:
            combined_summary = self._format_meals_summary(meals_today)

            return CalendarEvent(
                start=today,
                end=today + timedelta(days=1),
                summary=combined_summary,
                description=combined_summary,
            )
        else:
            return None

    def _format_meals_summary(self, meals: list[PlannedMeal]) -> str:
        """Format meals into a summary, grouping by meal type."""
        # Sort meals by their export_time (order in the day)
        sorted_meals = sorted(meals, key=lambda m: m["type"]["export_time"] or 0)

        # Group meals by meal type
        meals_by_type = {}
        for meal in sorted_meals:
            meal_type_name = meal["type"]["name"]
            if meal_type_name not in meals_by_type:
                meals_by_type[meal_type_name] = []
            meals_by_type[meal_type_name].append(meal["name"])

        # Format as "Meal Type: meal1, meal2"
        meal_summaries = [
            f"{meal_type}: {', '.join(meal_names)}"
            for meal_type, meal_names in meals_by_type.items()
        ]

        return ", ".join(meal_summaries)

    async def async_get_events(self, hass, start_date, end_date):
        LOGGER.info("@@@ Getting events for all meals")
        LOGGER.info(start_date)
        LOGGER.info(end_date)

        def filter_between_dates(m: PlannedMeal) -> bool:
            return start_date.date() <= m["date"] < end_date.date()

        meals_in_range = list(filter(filter_between_dates, self.coordinator.data.meals))

        # Group meals by date
        meals_by_date = {}
        for meal in meals_in_range:
            meal_date = meal["date"]
            if meal_date not in meals_by_date:
                meals_by_date[meal_date] = []
            meals_by_date[meal_date].append(meal)

        # Create one all-day event per date with all meals combined
        events = []
        for meal_date, meals in meals_by_date.items():
            combined_summary = self._format_meals_summary(meals)

            events.append(
                CalendarEvent(
                    start=meal_date,
                    end=meal_date + timedelta(days=1),
                    summary=combined_summary,
                    description=combined_summary,
                )
            )

        return events


async def async_setup_entry(
    hass: "HomeAssistant",  # noqa: ARG001 Unused function argument: `hass`
    entry: "PaprikaConfigEntry",
    async_add_entities: "AddEntitiesCallback",
) -> None:
    """Set up the sensor platform."""
    # Create individual meal type calendars
    entities = [
        PaprikaMealCalendar(
            coordinator=entry.runtime_data.coordinator,
            entry=entry,
            meal_type=mt,
        )
        for mt in entry.runtime_data.coordinator.data.meal_types
    ]

    # Add the combined all meals calendar
    entities.append(
        PaprikaAllMealsCalendar(
            coordinator=entry.runtime_data.coordinator,
            entry=entry,
        )
    )

    async_add_entities(entities)
