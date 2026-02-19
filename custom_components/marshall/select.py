"""Select platform for Marshall speakers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity, SelectEntityDescription

from .const import AUDIO_SOURCE_COMMANDS
from .entity import MarshallEntity
from .model_config import get_model_features

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import MarshallDataUpdateCoordinator
    from .data import MarshallConfigEntry


@dataclass(frozen=True, kw_only=True)
class MarshallSelectEntityDescription(SelectEntityDescription):
    """Describes a Marshall select entity."""


ENTITY_DESCRIPTIONS: tuple[MarshallSelectEntityDescription, ...] = (
    MarshallSelectEntityDescription(
        key="source",
        translation_key="source",
        icon="mdi:input-source",
        options=list(AUDIO_SOURCE_COMMANDS.keys()),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: MarshallConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities."""
    coordinator = entry.runtime_data.coordinator

    # Get features supported by this model
    model_features = get_model_features(coordinator.state.model)

    # Filter entities based on model
    entities_to_add = []
    for entity_description in ENTITY_DESCRIPTIONS:
        if entity_description.key == "source":
            # Build options based on model features
            options = []
            if model_features.get("bluetooth"):
                options.append("Bluetooth")
            if model_features.get("aux_input"):
                options.append("Aux")
            if model_features.get("rca_input"):
                options.append("RCA")

            if options:  # Only add if we have at least one option
                entities_to_add.append(
                    MarshallSelectEntity(
                        coordinator=coordinator,
                        entity_description=entity_description,
                        options=options,
                    )
                )

    async_add_entities(entities_to_add)


class MarshallSelectEntity(MarshallEntity, SelectEntity):
    """Representation of a select entity for Marshall speakers."""

    entity_description: MarshallSelectEntityDescription

    def __init__(
        self,
        coordinator: MarshallDataUpdateCoordinator,
        entity_description: MarshallSelectEntityDescription,
        options: list[str],
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}-{entity_description.key}"
        )
        self._attr_options = options

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self.entity_description.key == "source":
            return self.coordinator.state.source
        return None

    async def async_select_option(self, option: str) -> None:
        """Select new option."""
        if self.entity_description.key == "source":
            await self.coordinator.async_set_audio_source(option)
