"""DataUpdateCoordinator for Marshall Bluetooth speakers."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .ble import ActonBleError, BleClient
from .const import (
    AUDIO_SOURCE_COMMANDS,
    AUDIO_SOURCE_MAPPING,
    CHAR_BATTERY_LEVEL,
    CHAR_CONTROL,
    CHAR_DEVICE_NAME,
    CHAR_EQ,
    CHAR_FIRMWARE_REV,
    CHAR_HARDWARE_REV,
    CHAR_LED_BRIGHTNESS,
    CHAR_MEDIA_INFO,
    CHAR_MODEL_NUMBER,
    CHAR_SERIAL_NUMBER,
    CHAR_VOLUME,
    EQ_PRESET_NAMES,
    EQ_PRESETS,
    LED_BRIGHTNESS_OFFSET,
    LOGGER,
    MEDIA_INFO_ENTRY_MARKER_TERMINATOR,
    MEDIA_INFO_HEADER_SIZE,
    MEDIA_INFO_MAX_STRING_LENGTH,
    MEDIA_INFO_MIN_PARTS_FOR_FULL_FORMAT,
    NOTIFY_CHARACTERISTICS,
    PLAY_STATUS_MAPPING,
    STATUS_INDEX_PLAY_STATUS,
    STATUS_INDEX_SOURCE,
)
from .data import ActonState

MIN_DEVICE_NAME_DATA_LENGTH = 2

if TYPE_CHECKING:
    from .data import ActonConfigEntry


# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
class ActonDataUpdateCoordinator(DataUpdateCoordinator[ActonState]):
    """Class to manage BLE state for Marshall speakers."""

    config_entry: ActonConfigEntry

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the data update coordinator."""
        super().__init__(*args, update_interval=timedelta(minutes=5), **kwargs)
        self.state = ActonState()
        self._static_loaded = False
        self._notify_started = False

    @property
    def client(self) -> BleClient:
        """Return the BLE client instance."""
        return self.config_entry.runtime_data.client

    async def _async_update_data(self) -> ActonState:
        """Refresh state via BLE reads and notifications."""
        try:
            await self.client.async_connect()
            await self._ensure_notifications()
            await self._refresh_dynamic_state()
            if not self._static_loaded:
                await self._refresh_static_state()
                self._static_loaded = True
        except ActonBleError as exception:
            LOGGER.debug("BLE update failed: %s", exception)
            raise UpdateFailed(exception) from exception

        return self.state

    async def _ensure_notifications(self) -> None:
        if self._notify_started:
            return
        for uuid in NOTIFY_CHARACTERISTICS:
            try:
                await self.client.async_start_notify(uuid, self._handle_notify)
            except ActonBleError as exception:
                LOGGER.debug("BLE notify failed for %s: %s", uuid, exception)
        self._notify_started = True

    async def _refresh_dynamic_state(self) -> None:
        volume = await self._safe_read(CHAR_VOLUME)
        if volume:
            self.state.volume_step = volume[0]

        battery = await self._safe_read(CHAR_BATTERY_LEVEL)
        if battery:
            self.state.battery_level = battery[0]

        # Read control status for source and play state
        control = await self._safe_read(CHAR_CONTROL)
        if control and len(control) > STATUS_INDEX_PLAY_STATUS:
            self.state.source = AUDIO_SOURCE_MAPPING.get(control[STATUS_INDEX_SOURCE])
            status = PLAY_STATUS_MAPPING.get(control[STATUS_INDEX_PLAY_STATUS])
            self.state.is_playing = status == "playing" if status else None

    async def _refresh_static_state(self) -> None:
        self.state.device_name = self._decode_device_name(
            await self._safe_read(CHAR_DEVICE_NAME)
        )
        self.state.model = self._decode_str(await self._safe_read(CHAR_MODEL_NUMBER))
        self.state.serial = self._decode_str(await self._safe_read(CHAR_SERIAL_NUMBER))
        self.state.firmware = self._decode_str(await self._safe_read(CHAR_FIRMWARE_REV))
        self.state.hardware = self._decode_str(await self._safe_read(CHAR_HARDWARE_REV))

        # Read LED brightness
        led_data = await self._safe_read(CHAR_LED_BRIGHTNESS)
        if led_data:
            self.state.led_brightness = led_data[0] - LED_BRIGHTNESS_OFFSET

        # Read EQ preset
        eq_data = await self._safe_read(CHAR_EQ)
        if eq_data:
            self.state.eq_preset = self._decode_eq_preset(eq_data)

    def _handle_notify(self, uuid: str, data: bytes) -> None:
        if uuid == CHAR_VOLUME and data:
            self.state.volume_step = data[0]
        elif uuid == CHAR_CONTROL:
            self.state.control_raw = data
            # Decode control status for source and play state
            if data and len(data) > STATUS_INDEX_PLAY_STATUS:
                self.state.source = AUDIO_SOURCE_MAPPING.get(data[STATUS_INDEX_SOURCE])
                status = PLAY_STATUS_MAPPING.get(data[STATUS_INDEX_PLAY_STATUS])
                self.state.is_playing = status == "playing" if status else None
        elif uuid == CHAR_MEDIA_INFO:
            # Ignore terminator pattern to keep the latest media info
            if not (
                data == b"\x00\x00\x00\xff\x00\x00\x00\x00"
                or data.startswith(b"\x00\x00\x00\xff")
            ):
                self.state.media_info = self._decode_media_info(data)
        elif uuid == CHAR_EQ:
            self.state.eq_raw = data
            self.state.eq_preset = self._decode_eq_preset(data)
        else:
            self.state.unknown_notify[uuid] = data

        self.async_set_updated_data(self.state)

    async def _safe_read(self, uuid: str) -> bytes:
        try:
            return await self.client.async_read(uuid)
        except ActonBleError as exception:
            LOGGER.debug("BLE read failed for %s: %s", uuid, exception)
            return b""

    async def async_set_led_brightness(self, brightness: int) -> None:
        """Set LED brightness (0-35)."""
        raw_value = brightness + LED_BRIGHTNESS_OFFSET
        try:
            await self.client.async_write(
                CHAR_LED_BRIGHTNESS, bytes([raw_value]), response=True
            )
            self.state.led_brightness = brightness
            self.async_set_updated_data(self.state)
        except ActonBleError as exception:
            LOGGER.debug("Failed to set LED brightness: %s", exception)

    async def async_set_audio_source(self, source: str) -> None:
        """Set audio source (Bluetooth, Aux, or RCA)."""
        if source not in AUDIO_SOURCE_COMMANDS:
            LOGGER.warning("Invalid audio source: %s", source)
            return
        command = AUDIO_SOURCE_COMMANDS[source]
        try:
            await self.client.async_write(CHAR_CONTROL, bytes([command]), response=True)
            self.state.source = source
            self.async_set_updated_data(self.state)
        except ActonBleError as exception:
            LOGGER.debug("Failed to set audio source: %s", exception)

    async def async_set_eq_preset(self, preset: str) -> None:
        """Set EQ preset (Flat, Bright, Warm, Voice)."""
        if preset not in EQ_PRESETS:
            LOGGER.warning("Invalid EQ preset: %s", preset)
            return
        command = EQ_PRESETS[preset]
        try:
            await self.client.async_write(CHAR_EQ, bytes([command]), response=False)
            self.state.eq_preset = preset
            self.async_set_updated_data(self.state)
        except ActonBleError as exception:
            LOGGER.debug("Failed to set EQ preset: %s", exception)

    @staticmethod
    def _decode_str(data: bytes) -> str | None:
        if not data:
            return None
        try:
            return data.decode(errors="ignore").strip("\x00").strip()
        except UnicodeDecodeError:
            return None

    @staticmethod
    def _decode_eq_preset(data: bytes) -> str | None:
        """Decode EQ preset from single-byte value."""
        if not data or len(data) == 0:
            return None
        preset_value = data[0]
        return EQ_PRESET_NAMES.get(preset_value)

    @staticmethod
    def _decode_device_name(data: bytes) -> str | None:
        if not data:
            return None
        if data[0] != 0x01:
            return ActonDataUpdateCoordinator._decode_str(data)
        if len(data) < MIN_DEVICE_NAME_DATA_LENGTH:
            return None
        length = data[1]
        if length == 0:
            return ""
        start = 2
        end = min(len(data), start + length)
        return ActonDataUpdateCoordinator._decode_str(data[start:end])

    @staticmethod
    def _decode_media_info(data: bytes) -> str | None:
        """
        Decode media info characteristic data.

        Format:
        - 4 bytes: entry marker (00000001, 00000002, 00000003, or ff terminator)
        - 2 bytes: type/format indicator (e.g., 006a)
        - 2 bytes: string length (big-endian)
        - N bytes: string data (UTF-8)
        - Repeat entries or terminate with ff

        Entries: Title (001), Artist (002), Album (003)
        """
        if not data or len(data) < MEDIA_INFO_HEADER_SIZE:
            return None

        # Check for empty/terminator pattern
        if data == b"\x00\x00\x00\xff\x00\x00\x00\x00" or data.startswith(
            b"\x00\x00\x00\xff"
        ):
            return None

        parts = []
        offset = 0

        try:
            while offset < len(data):
                # Need at least header size: 4 (marker) + 2 (type) + 2 (length)
                if offset + MEDIA_INFO_HEADER_SIZE > len(data):
                    break

                # Read entry marker (4 bytes, big-endian)
                marker = int.from_bytes(data[offset : offset + 4], "big")
                offset += 4

                # Check for terminator
                if marker in {MEDIA_INFO_ENTRY_MARKER_TERMINATOR, 0}:
                    break

                # Skip type indicator (2 bytes)
                offset += 2

                # Read string length (2 bytes, big-endian)
                str_length = int.from_bytes(data[offset : offset + 2], "big")
                offset += 2

                # Sanity check for string length
                if (
                    str_length == 0
                    or str_length > MEDIA_INFO_MAX_STRING_LENGTH
                    or offset + str_length > len(data)
                ):
                    break

                # Extract and decode string
                string_data = data[offset : offset + str_length]
                decoded = ActonDataUpdateCoordinator._decode_str(string_data)

                if decoded:
                    parts.append(decoded)

                offset += str_length
        except (IndexError, ValueError, OverflowError):
            pass

        # If we extracted parts, return them formatted
        if len(parts) >= MEDIA_INFO_MIN_PARTS_FOR_FULL_FORMAT:
            return f"{parts[0]} - {parts[1]} ({parts[2]})"  # Title - Artist (Album)
        if parts:
            return " - ".join(parts)

        # Fallback to hex representation only if we have actual data
        if data and data != b"\x00" * len(data):
            return data.hex()

        return None
