"""Number platform for Marshall speakers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import EntityCategory

from .const import LED_BRIGHTNESS_MAX, LED_BRIGHTNESS_MIN
from .entity import ActonEntity
from .model_config import get_model_features

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import ActonDataUpdateCoordinator
    from .data import ActonConfigEntry


@dataclass(frozen=True, kw_only=True)
class ActonNumberEntityDescription(NumberEntityDescription):
    """Describes an Acton number entity."""


ENTITY_DESCRIPTIONS: tuple[ActonNumberEntityDescription, ...] = (
    ActonNumberEntityDescription(
        key="led_brightness",
        translation_key="led_brightness",
        entity_category=EntityCategory.CONFIG,
        native_min_value=LED_BRIGHTNESS_MIN,
        native_max_value=LED_BRIGHTNESS_MAX,
        native_step=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: ActonConfigEntry,
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
            ActonNumberEntity(
                coordinator=coordinator,
                entity_description=entity_description,
            )
        )

    async_add_entities(entities_to_add)


class ActonNumberEntity(ActonEntity, NumberEntity):
    """Representation of a number entity for Marshall speakers."""

    entity_description: ActonNumberEntityDescription

    def __init__(
        self,
        coordinator: ActonDataUpdateCoordinator,
        entity_description: ActonNumberEntityDescription,
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
        return getattr(self.coordinator.state, self.entity_description.key)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if self.entity_description.key == "led_brightness":
            await self.coordinator.async_set_led_brightness(int(value))
