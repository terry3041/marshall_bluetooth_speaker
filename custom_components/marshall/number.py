"""Number platform for Marshall speakers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory

from .const import (
    EQ_BAND_COUNT,
    EQ_BAND_MAX,
    EQ_BAND_MIN,
    FEATURE_LED_BRIGHTNESS,
    LED_BRIGHTNESS_MAX,
    LED_BRIGHTNESS_MIN,
)
from .entity import MarshallEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import MarshallDataUpdateCoordinator
    from .data import MarshallConfigEntry


@dataclass(frozen=True, kw_only=True)
class MarshallNumberEntityDescription(NumberEntityDescription):
    """Describes a Marshall number entity."""

    eq_band: int | None = None


LED_BRIGHTNESS_DESCRIPTION = MarshallNumberEntityDescription(
    key="led_brightness",
    translation_key="led_brightness",
    entity_category=EntityCategory.CONFIG,
    native_min_value=LED_BRIGHTNESS_MIN,
    native_max_value=LED_BRIGHTNESS_MAX,
    native_step=1,
    mode=NumberMode.SLIDER,
)

EQ_BAND_ICONS = (
    "mdi:speaker",
    "mdi:equalizer-outline",
    "mdi:equalizer",
    "mdi:equalizer-outline",
    "mdi:music-clef-treble",
)

EQ_DESCRIPTIONS: tuple[MarshallNumberEntityDescription, ...] = tuple(
    MarshallNumberEntityDescription(
        key=f"eq_band_{band}",
        translation_key=f"eq_band_{band}",
        icon=EQ_BAND_ICONS[band],
        native_min_value=EQ_BAND_MIN,
        native_max_value=EQ_BAND_MAX,
        native_step=1,
        mode=NumberMode.SLIDER,
        eq_band=band,
    )
    for band in range(EQ_BAND_COUNT)
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: MarshallConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    coordinator = entry.runtime_data.coordinator

    descriptions: list[MarshallNumberEntityDescription] = []
    if coordinator.supports(FEATURE_LED_BRIGHTNESS):
        descriptions.append(LED_BRIGHTNESS_DESCRIPTION)
    # Only expose EQ bands the speaker actually has (e.g. Acton III: bass/treble)
    bands = coordinator.state.eq_bands
    descriptions.extend(
        description
        for description in EQ_DESCRIPTIONS
        if description.eq_band is not None
        and description.eq_band < len(bands)
        and bands[description.eq_band] is not None
    )

    async_add_entities(
        MarshallNumberEntity(coordinator=coordinator, entity_description=description)
        for description in descriptions
    )


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
        band = self.entity_description.eq_band
        if band is not None:
            bands = self.coordinator.state.eq_bands
            if band < len(bands) and bands[band] is not None:
                return float(bands[band])
            return None
        return getattr(self.coordinator.state, self.entity_description.key, None)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        band = self.entity_description.eq_band
        if band is not None:
            await self.coordinator.async_set_equaliser_band(band, int(value))
        elif self.entity_description.key == "led_brightness":
            await self.coordinator.async_set_led_brightness(int(value))
