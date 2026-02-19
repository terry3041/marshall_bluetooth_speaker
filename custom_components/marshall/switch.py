"""Switch platform for Marshall speakers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory

from .entity import MarshallEntity
from .model_config import get_model_features

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import MarshallDataUpdateCoordinator
    from .data import MarshallConfigEntry


@dataclass(frozen=True, kw_only=True)
class MarshallSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Marshall switch entity."""


ENTITY_DESCRIPTIONS: tuple[MarshallSwitchEntityDescription, ...] = (
    MarshallSwitchEntityDescription(
        key="interaction_sounds",
        translation_key="interaction_sounds",
        icon="mdi:bell-ring",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: MarshallConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities."""
    coordinator = entry.runtime_data.coordinator

    # Get features supported by this model
    model_features = get_model_features(coordinator.state.model)

    # Filter entities based on model support
    entities_to_add = []
    for entity_description in ENTITY_DESCRIPTIONS:
        if entity_description.key == "interaction_sounds" and not model_features.get(
            "interaction_sounds"
        ):
            continue
        entities_to_add.append(
            MarshallSwitchEntity(
                coordinator=coordinator,
                entity_description=entity_description,
            )
        )

    async_add_entities(entities_to_add)


class MarshallSwitchEntity(MarshallEntity, SwitchEntity):
    """Representation of a switch entity for Marshall speakers."""

    entity_description: MarshallSwitchEntityDescription

    def __init__(
        self,
        coordinator: MarshallDataUpdateCoordinator,
        entity_description: MarshallSwitchEntityDescription,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}-{entity_description.key}"
        )

    @property
    def is_on(self) -> bool | None:
        """Return the current state."""
        if self.entity_description.key == "interaction_sounds":
            return self.coordinator.state.interaction_sounds
        return None

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Turn on the switch."""
        if self.entity_description.key == "interaction_sounds":
            await self.coordinator.async_set_interaction_sounds(enabled=True)

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn off the switch."""
        if self.entity_description.key == "interaction_sounds":
            await self.coordinator.async_set_interaction_sounds(enabled=False)
