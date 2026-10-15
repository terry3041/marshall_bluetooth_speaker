"""Sensor platform for Marshall speakers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory

from .entity import MarshallEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import MarshallDataUpdateCoordinator
    from .data import MarshallConfigEntry

ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        key="model",
        translation_key="model",
        entity_registry_enabled_default=False,
        icon="mdi:information",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="serial",
        translation_key="serial",
        entity_registry_enabled_default=False,
        icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="firmware",
        translation_key="firmware",
        entity_registry_enabled_default=False,
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="hardware",
        translation_key="hardware",
        entity_registry_enabled_default=False,
        icon="mdi:memory",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: MarshallConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        MarshallSensor(
            coordinator=coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class MarshallSensor(MarshallEntity, SensorEntity):
    """Marshall speakers sensor class."""

    def __init__(
        self,
        coordinator: MarshallDataUpdateCoordinator,
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
