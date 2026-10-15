"""Media player platform for Marshall speakers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
)
from homeassistant.components.media_player.const import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)

from .ble import MarshallBleError
from .const import (
    CHAR_CONTROL,
    CHAR_FCCD_AUDIO_CONTROL,
    CMD_NEXT,
    CMD_PAUSE,
    CMD_PLAY,
    CMD_PREVIOUS,
    LOGGER,
)
from .entity import MarshallEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import MarshallDataUpdateCoordinator
    from .data import MarshallConfigEntry

BASE_FEATURES = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: MarshallConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the media_player platform."""
    async_add_entities([MarshallMediaPlayer(entry.runtime_data.coordinator)])


class MarshallMediaPlayer(MarshallEntity, MediaPlayerEntity):
    """Marshall speakers media player entity."""

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_name = None

    def __init__(self, coordinator: MarshallDataUpdateCoordinator) -> None:
        """Initialize the media player entity with its coordinator."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-media_player"

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return supported features (source selection only if >1 source)."""
        features = BASE_FEATURES
        if len(self.coordinator.source_options) > 1:
            features |= MediaPlayerEntityFeature.SELECT_SOURCE
        return features

    @property
    def available(self) -> bool:
        """Return True if the speaker is connected."""
        return self.coordinator.client.is_connected

    @property
    def state(self) -> MediaPlayerState:
        """Return the current media player state."""
        state = self.coordinator.state
        if state.source not in (None, "Bluetooth"):
            # Analog inputs have no transport state; the speaker is just on.
            return MediaPlayerState.ON
        if state.is_playing is True:
            return MediaPlayerState.PLAYING
        if state.is_playing is False:
            return MediaPlayerState.PAUSED
        return MediaPlayerState.IDLE

    @property
    def volume_level(self) -> float | None:
        """Return the current volume level (0.0 to 1.0)."""
        step = self.coordinator.state.volume_step
        if step is None:
            return None
        return max(0.0, min(1.0, step / self.coordinator.state.volume_max))

    @property
    def volume_step(self) -> float:
        """Return one hardware volume step as a fraction."""
        return 1 / self.coordinator.state.volume_max

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self.coordinator.state.source

    @property
    def source_list(self) -> list[str]:
        """Return the selectable input sources."""
        return self.coordinator.source_options

    def _bluetooth_media(self) -> bool:
        return self.coordinator.state.source in (None, "Bluetooth")

    @property
    def media_content_type(self) -> MediaType | None:
        """Return the content type of current playing media."""
        return MediaType.MUSIC if self.media_title else None

    @property
    def media_title(self) -> str | None:
        """Return the title of current playing media."""
        if not self._bluetooth_media():
            return None
        state = self.coordinator.state
        if state.media_title or state.media_artist:
            return state.media_title
        return state.media_info

    @property
    def media_artist(self) -> str | None:
        """Return the artist of current playing media."""
        if not self._bluetooth_media():
            return None
        return self.coordinator.state.media_artist

    @property
    def media_album_name(self) -> str | None:
        """Return the album of current playing media."""
        if not self._bluetooth_media():
            return None
        return self.coordinator.state.media_album

    async def async_media_play(self) -> None:
        """Send play command to the media player."""
        await self._send_control(CMD_PLAY)

    async def async_media_pause(self) -> None:
        """Send pause command to the media player."""
        await self._send_control(CMD_PAUSE)

    async def async_media_next_track(self) -> None:
        """Send next track command to the media player."""
        await self._send_control(CMD_NEXT)

    async def async_media_previous_track(self) -> None:
        """Send previous track command to the media player."""
        await self._send_control(CMD_PREVIOUS)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level (0.0 to 1.0)."""
        volume_max = self.coordinator.state.volume_max
        await self.coordinator.async_set_volume_step(round(volume * volume_max))

    async def async_volume_up(self) -> None:
        """Turn volume up by one hardware step."""
        step = self.coordinator.state.volume_step or 0
        await self.coordinator.async_set_volume_step(step + 1)

    async def async_volume_down(self) -> None:
        """Turn volume down by one hardware step."""
        step = self.coordinator.state.volume_step or 0
        await self.coordinator.async_set_volume_step(step - 1)

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self.coordinator.async_set_audio_source(source)

    async def _send_control(self, command: int) -> None:
        uuid = self.coordinator._char(CHAR_CONTROL, CHAR_FCCD_AUDIO_CONTROL)  # noqa: SLF001
        try:
            await self.coordinator.client.async_write(
                uuid, bytes([command]), response=True
            )
        except MarshallBleError as exception:
            LOGGER.debug("BLE write failed for %s: %s", uuid, exception)
            return
        if command in (CMD_PLAY, CMD_PAUSE):
            self.coordinator.state.is_playing = command == CMD_PLAY
            self.coordinator.async_set_updated_data(self.coordinator.state)
