"""Number platform for Marshall speakers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import EntityCategory

from .const import (
    EQ_BAND_MAX,
    EQ_BAND_MIN,
    LED_BRIGHTNESS_MAX,
    LED_BRIGHTNESS_MIN,
)
from .entity import MarshallEntity
from .model_config import get_model_features

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import MarshallDataUpdateCoordinator
    from .data import MarshallConfigEntry


@dataclass(frozen=True, kw_only=True)
class MarshallNumberEntityDescription(NumberEntityDescription):
    """Describes a Marshall number entity."""


ENTITY_DESCRIPTIONS: tuple[MarshallNumberEntityDescription, ...] = (
    MarshallNumberEntityDescription(
        key="led_brightness",
        translation_key="led_brightness",
        entity_category=EntityCategory.CONFIG,
        native_min_value=LED_BRIGHTNESS_MIN,
        native_max_value=LED_BRIGHTNESS_MAX,
        native_step=1,
    ),
    MarshallNumberEntityDescription(
        key="eq_band_0",
        translation_key="eq_band_0",
        entity_category=EntityCategory.CONFIG,
        native_min_value=EQ_BAND_MIN,
        native_max_value=EQ_BAND_MAX,
        native_step=1,
    ),
    MarshallNumberEntityDescription(
        key="eq_band_1",
        translation_key="eq_band_1",
        entity_category=EntityCategory.CONFIG,
        native_min_value=EQ_BAND_MIN,
        native_max_value=EQ_BAND_MAX,
        native_step=1,
    ),
    MarshallNumberEntityDescription(
        key="eq_band_2",
        translation_key="eq_band_2",
        entity_category=EntityCategory.CONFIG,
        native_min_value=EQ_BAND_MIN,
        native_max_value=EQ_BAND_MAX,
        native_step=1,
    ),
    MarshallNumberEntityDescription(
        key="eq_band_3",
        translation_key="eq_band_3",
        entity_category=EntityCategory.CONFIG,
        native_min_value=EQ_BAND_MIN,
        native_max_value=EQ_BAND_MAX,
        native_step=1,
    ),
    MarshallNumberEntityDescription(
        key="eq_band_4",
        translation_key="eq_band_4",
        entity_category=EntityCategory.CONFIG,
        native_min_value=EQ_BAND_MIN,
        native_max_value=EQ_BAND_MAX,
        native_step=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: MarshallConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    coordinator = entry.runtime_data.coordinator

    # Get features supported by this model
    model_features = get_model_features(coordinator.state.model)

    # Filter entities based on model support
    entities_to_add = []
    for entity_description in ENTITY_DESCRIPTIONS:
        if entity_description.key == "led_brightness" and not model_features.get(
            "led_brightness"
        ):
            continue
        entities_to_add.append(
            MarshallNumberEntity(
                coordinator=coordinator,
                entity_description=entity_description,
            )
        )

    async_add_entities(entities_to_add)


class MarshallNumberEntity(MarshallEntity, NumberEntity):
    """Representation of a number entity for Marshall speakers."""

    entity_description: MarshallNumberEntityDescription

    def __init__(
        self,
        coordinator: MarshallDataUpdateCoordinator,
        entity_description: MarshallNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}-{entity_description.key}"
        )

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        # Handle EQ bands
        if self.entity_description.key.startswith("eq_band_"):
            band_index = int(self.entity_description.key.split("_")[-1])
            if band_index < len(self.coordinator.state.eq_bands):
                return float(self.coordinator.state.eq_bands[band_index])
            return None

        return getattr(self.coordinator.state, self.entity_description.key, None)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if self.entity_description.key == "led_brightness":
            await self.coordinator.async_set_led_brightness(int(value))
        elif self.entity_description.key.startswith("eq_band_"):
            # Update the specific EQ band
            band_index = int(self.entity_description.key.split("_")[-1])
            if band_index < len(self.coordinator.state.eq_bands):
                new_bands = self.coordinator.state.eq_bands.copy()
                new_bands[band_index] = int(value)
                await self.coordinator.async_set_equaliser_profile(new_bands)
