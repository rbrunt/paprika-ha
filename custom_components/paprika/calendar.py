from typing import TYPE_CHECKING
from homeassistant.components.calendar import CalendarEntity, CalendarEvent


from custom_components.paprika import PaprikaConfigEntry
from custom_components.paprika.api import MealType, PlannedMeal
from custom_components.paprika.coordinator import PaprikaCoordinator
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from datetime import datetime, timedelta


if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


def filter_by_type(m: PlannedMeal, meal_type: MealType) -> bool:
    return m["type"] == meal_type


def filter_between_dates(
    m: PlannedMeal, start_date: datetime, end_date: datetime
) -> bool:
    return start_date <= m["date"] < end_date


class PaprikaMealCalendar(CalendarEntity, CoordinatorEntity[PaprikaCoordinator]):

    def __init__(self, coordinator: PaprikaCoordinator, meal_type: MealType):
        super().__init__(coordinator)
        self.meal_type = meal_type
        self.entity_description = f"Calendar for {meal_type.name}"

    def async_get_events(self, hass, start_date, end_date):

        meals = filter(filter_by_type, self.coordinator.meals)
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
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: PaprikaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_entities(
        [
            PaprikaMealCalendar(
                coordinator=entry.runtime_data.coordinator, meal_type=MealType.Dinner
            )
        ]
    )
