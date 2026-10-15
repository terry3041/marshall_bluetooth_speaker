"""Switch platform for Marshall speakers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory

from .const import FEATURE_INTERACTION_SOUNDS, FEATURE_NIGHT_MODE
from .entity import MarshallEntity

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
        key=FEATURE_INTERACTION_SOUNDS,
        translation_key=FEATURE_INTERACTION_SOUNDS,
        icon="mdi:bell-ring",
        entity_category=EntityCategory.CONFIG,
    ),
    MarshallSwitchEntityDescription(
        key=FEATURE_NIGHT_MODE,
        translation_key=FEATURE_NIGHT_MODE,
        icon="mdi:weather-night",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: MarshallConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities supported by this speaker."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        MarshallSwitchEntity(coordinator=coordinator, entity_description=description)
        for description in ENTITY_DESCRIPTIONS
        if coordinator.supports(description.key)
    )


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
        return getattr(self.coordinator.state, self.entity_description.key, None)

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Turn on the switch."""
        await self._async_set(enabled=True)

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn off the switch."""
        await self._async_set(enabled=False)

    async def _async_set(self, *, enabled: bool) -> None:
        if self.entity_description.key == FEATURE_INTERACTION_SOUNDS:
            await self.coordinator.async_set_interaction_sounds(enabled=enabled)
        elif self.entity_description.key == FEATURE_NIGHT_MODE:
            await self.coordinator.async_set_night_mode(enabled=enabled)
