"""Sensor platform for Marshall speakers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory

from .entity import ActonEntity
from .model_config import get_model_features

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import ActonDataUpdateCoordinator
    from .data import ActonConfigEntry

ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        key="model",
        name="Model",
        icon="mdi:information",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="serial",
        name="Serial",
        icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="firmware",
        name="Firmware",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="hardware",
        name="Hardware",
        icon="mdi:memory",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: ActonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data.coordinator

    # Get features supported by this model (for future use in filtering)
    get_model_features(coordinator.state.model)

    async_add_entities(
        ActonSensor(
            coordinator=coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class ActonSensor(ActonEntity, SensorEntity):
    """Marshall speakers sensor class."""

    def __init__(
        self,
        coordinator: ActonDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}-{entity_description.key}"
        )

    @property
    def native_value(self) -> str | int | None:
        """Return the native value of the sensor."""
        state = self.coordinator.state
        key = self.entity_description.key
        attr_map = {
            "model": state.model,
            "serial": state.serial,
            "firmware": state.firmware,
            "hardware": state.hardware,
        }
        return attr_map.get(key)
