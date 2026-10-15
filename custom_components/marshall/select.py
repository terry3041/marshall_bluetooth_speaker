"""Select platform for Marshall speakers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory

from .const import FEATURE_ROOM_PLACEMENT, ROOM_PLACEMENT_OPTIONS
from .entity import MarshallEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import MarshallDataUpdateCoordinator
    from .data import MarshallConfigEntry

ROOM_PLACEMENT_VALUES = {
    option: value for value, option in ROOM_PLACEMENT_OPTIONS.items()
}


@dataclass(frozen=True, kw_only=True)
class MarshallSelectEntityDescription(SelectEntityDescription):
    """Describes a Marshall select entity."""


SOURCE_DESCRIPTION = MarshallSelectEntityDescription(
    key="source",
    translation_key="source",
    icon="mdi:import",
)

ROOM_PLACEMENT_DESCRIPTION = MarshallSelectEntityDescription(
    key="room_placement",
    translation_key="room_placement",
    icon="mdi:sofa-single",
    entity_category=EntityCategory.CONFIG,
    options=list(ROOM_PLACEMENT_OPTIONS.values()),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: MarshallConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities."""
    coordinator = entry.runtime_data.coordinator

    entities: list[SelectEntity] = []
    if len(coordinator.source_options) > 1:
        entities.append(MarshallSourceSelect(coordinator, SOURCE_DESCRIPTION))
    if coordinator.supports(FEATURE_ROOM_PLACEMENT):
        entities.append(
            MarshallRoomPlacementSelect(coordinator, ROOM_PLACEMENT_DESCRIPTION)
        )
    async_add_entities(entities)


class MarshallSelectEntity(MarshallEntity, SelectEntity):
    """Base select entity for Marshall speakers."""

    entity_description: MarshallSelectEntityDescription

    def __init__(
        self,
        coordinator: MarshallDataUpdateCoordinator,
        entity_description: MarshallSelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}-{entity_description.key}"
        )


class MarshallSourceSelect(MarshallSelectEntity):
    """Audio source select."""

    @property
    def options(self) -> list[str]:
        """Return the selectable sources."""
        return self.coordinator.source_options

    @property
    def current_option(self) -> str | None:
        """Return the current source."""
        source = self.coordinator.state.source
        return source if source in self.options else None

    async def async_select_option(self, option: str) -> None:
        """Select a new source."""
        await self.coordinator.async_set_audio_source(option)


class MarshallRoomPlacementSelect(MarshallSelectEntity):
    """Placement compensation select (Gen III)."""

    @property
    def current_option(self) -> str | None:
        """Return the current placement."""
        value = self.coordinator.state.room_placement
        return ROOM_PLACEMENT_OPTIONS.get(value) if value is not None else None

    async def async_select_option(self, option: str) -> None:
        """Select a new placement."""
        await self.coordinator.async_set_room_placement(ROOM_PLACEMENT_VALUES[option])
