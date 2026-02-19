"""Media player platform for Marshall speakers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.media_player import (
    MediaPlayerEntity,
)
from homeassistant.components.media_player.const import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
)

from .ble import MarshallBleError
from .const import (
    CHAR_CONTROL,
    CHAR_VOLUME,
    CMD_NEXT,
    CMD_PAUSE,
    CMD_PLAY,
    CMD_PREVIOUS,
    LOGGER,
    VOLUME_MAX,
)
from .entity import MarshallEntity
from .model_config import get_model_features

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import MarshallDataUpdateCoordinator
    from .data import MarshallConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: MarshallConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the media_player platform."""
    coordinator = entry.runtime_data.coordinator

    # Get features supported by this model (for future use in filtering)
    get_model_features(coordinator.state.model)

    async_add_entities([MarshallMediaPlayer(coordinator)])


class MarshallMediaPlayer(MarshallEntity, MediaPlayerEntity):
    """Marshall speakers media player entity."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.VOLUME_SET
    )

    def __init__(self, coordinator: MarshallDataUpdateCoordinator) -> None:
        """Initialize the media player entity with its coordinator."""
        super().__init__(coordinator)
        self._attr_name = None
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-media_player"

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return self.coordinator.client.is_connected

    @property
    def state(self) -> str:
        """Return the current media player state."""
        if not self.available:
            return MediaPlayerState.OFF
        if self.coordinator.state.is_playing is True:
            return MediaPlayerState.PLAYING
        if self.coordinator.state.is_playing is False:
            return MediaPlayerState.PAUSED
        return MediaPlayerState.ON

    @property
    def volume_level(self) -> float | None:
        """Return the current volume level (0.0 to 1.0)."""
        step = self.coordinator.state.volume_step
        if step is None:
            return None
        return max(0.0, min(1.0, step / VOLUME_MAX))

    @property
    def media_title(self) -> str | None:
        """Return the title of current playing media."""
        # Only show media info when source is Bluetooth
        if self.coordinator.state.source != "Bluetooth":
            return None
        return self.coordinator.state.media_info

    @property
    def media_artist(self) -> str | None:
        """Return the artist of current playing media."""
        return None

    @property
    def media_album_name(self) -> str | None:
        """Return the album name of current playing media."""
        return None

    async def async_turn_on(self) -> None:
        """Turn on the media player."""
        await self.coordinator.client.async_connect()

    async def async_turn_off(self) -> None:
        """Turn off the media player."""
        await self.coordinator.client.async_disconnect()

    async def async_media_play(self) -> None:
        """Send play command to the media player."""
        await self._safe_write(CHAR_CONTROL, bytes([CMD_PLAY]), response=True)

    async def async_media_pause(self) -> None:
        """Send pause command to the media player."""
        await self._safe_write(CHAR_CONTROL, bytes([CMD_PAUSE]), response=True)

    async def async_media_next_track(self) -> None:
        """Send next track command to the media player."""
        await self._safe_write(CHAR_CONTROL, bytes([CMD_NEXT]), response=True)

    async def async_media_previous_track(self) -> None:
        """Send previous track command to the media player."""
        await self._safe_write(CHAR_CONTROL, bytes([CMD_PREVIOUS]), response=True)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level (0.0 to 1.0)."""
        step = round(max(0.0, min(1.0, volume)) * VOLUME_MAX)
        await self._safe_write(CHAR_VOLUME, bytes([step]), response=True)

    async def _safe_write(
        self, uuid: str, data: bytes, *, response: bool = False
    ) -> None:
        try:
            await self.coordinator.client.async_write(uuid, data, response=response)
        except MarshallBleError as exception:
            LOGGER.debug("BLE write failed for %s: %s", uuid, exception)
