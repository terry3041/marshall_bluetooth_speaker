"""DataUpdateCoordinator for Marshall Bluetooth speakers."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .ble import BleClient, MarshallBleError
from .const import (
    AUDIO_SOURCE_COMMANDS,
    AUDIO_SOURCE_MAPPING,
    CHAR_BATTERY_LEVEL,
    CHAR_CONTROL,
    CHAR_DEVICE_NAME,
    CHAR_EQ,
    CHAR_FCCD_AUDIO_CONTROL,
    CHAR_FCCD_EQ,
    CHAR_FCCD_NIGHT_MODE,
    CHAR_FCCD_NOW_PLAYING,
    CHAR_FCCD_PAIRING,
    CHAR_FCCD_RENAME,
    CHAR_FCCD_ROOM_PLACEMENT,
    CHAR_FCCD_SOURCE,
    CHAR_FCCD_VOLUME,
    CHAR_FCCD_VOLUME_LIMIT,
    CHAR_FIRMWARE_REV,
    CHAR_HARDWARE_REV,
    CHAR_LED_BRIGHTNESS,
    CHAR_MEDIA_INFO,
    CHAR_MODEL_NUMBER,
    CHAR_PAIRING,
    CHAR_SERIAL_NUMBER,
    CHAR_VOLUME,
    DEVICE_NAME_MAX_LENGTH,
    EQ_BAND_COUNT,
    FCCD_AUDIO_SOURCE_COMMANDS,
    FCCD_AUDIO_SOURCE_MAPPING,
    FCCD_FEATURE_CHARACTERISTICS,
    FCCD_SOURCE_SCHEME2_INDEX,
    FCCD_SOURCE_SCHEME2_MARKER,
    FCCD_SOURCE_SCHEME2_MIN_LENGTH,
    FCCD_VOLUME_MAX_DEFAULT,
    FEATURE_INTERACTION_SOUNDS,
    FEATURE_LED_BRIGHTNESS,
    FEATURE_NIGHT_MODE,
    FEATURE_ROOM_PLACEMENT,
    LED_BRIGHTNESS_OFFSET,
    LOGGER,
    MEDIA_ENTRY_ALBUM,
    MEDIA_ENTRY_ARTIST,
    MEDIA_ENTRY_TITLE,
    MEDIA_INFO_ENTRY_MARKER_TERMINATOR,
    MEDIA_INFO_HEADER_SIZE,
    MEDIA_INFO_MAX_STRING_LENGTH,
    MEDIA_INFO_MIN_PARTS_FOR_FULL_FORMAT,
    MEDIA_NOT_PROVIDED,
    PLAY_STATUS_MAPPING,
    ROOM_PLACEMENT_OPTIONS,
    STATUS_INDEX_INTERACTION_SOUND,
    STATUS_INDEX_PLAY_STATUS,
    STATUS_INDEX_SOURCE,
    VOLUME_MAX,
)
from .data import MarshallState
from .model_config import get_model_features

MIN_DEVICE_NAME_DATA_LENGTH = 2
RECONNECT_DELAY_SECONDS = 5
MAX_SANE_VOLUME_STEPS = 100
EQ_BAND_MAX_VALUE = 10
# 0xFF means "unused/neutral" for FCCD EQ bands
EQ_BAND_UNUSED = 0xFF

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable

    from .data import MarshallConfigEntry


class MarshallDataUpdateCoordinator(DataUpdateCoordinator[MarshallState]):
    """Class to manage BLE state for Marshall speakers."""

    config_entry: MarshallConfigEntry

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the data update coordinator."""
        super().__init__(*args, update_interval=timedelta(minutes=5), **kwargs)
        self.state = MarshallState()
        self._static_loaded = False
        self._notify_started = False
        self._is_fccd = (
            False  # True for Gen III+ (FCCD protocol), False for Gen II (FE8F)
        )
        self._fccd_features: set[str] = set()
        self._unsub_disconnect: Callable[[], None] | None = None
        self._reconnect_handle: asyncio.TimerHandle | None = None

    @property
    def is_fccd(self) -> bool:
        """Return True if the speaker uses the Gen III (FCCD) protocol."""
        return self._is_fccd

    def supports(self, feature: str) -> bool:
        """Return whether the connected speaker supports a feature."""
        if self._is_fccd:
            return feature in self._fccd_features
        model_features = get_model_features(self.state.model)
        if feature in (FEATURE_LED_BRIGHTNESS, FEATURE_INTERACTION_SOUNDS):
            return bool(model_features.get(feature))
        return False

    @property
    def source_options(self) -> list[str]:
        """Return the audio sources selectable on this model."""
        model_features = get_model_features(self.state.model)
        options = []
        if model_features.get("bluetooth"):
            options.append("Bluetooth")
        if model_features.get("aux_input"):
            options.append("Aux")
        if model_features.get("rca_input"):
            options.append("RCA")
        return options

    @callback
    def _handle_unexpected_disconnect(self) -> None:
        """Re-subscribe and refresh soon after the speaker drops the link."""
        self._notify_started = False
        self.async_update_listeners()
        if self._reconnect_handle:
            self._reconnect_handle.cancel()
        self._reconnect_handle = self.hass.loop.call_later(
            RECONNECT_DELAY_SECONDS,
            lambda: self.hass.async_create_task(self.async_request_refresh()),
        )

    @callback
    def async_shutdown_reconnect(self) -> None:
        """Cancel reconnect handling (on unload)."""
        if self._reconnect_handle:
            self._reconnect_handle.cancel()
            self._reconnect_handle = None
        if self._unsub_disconnect:
            self._unsub_disconnect()
            self._unsub_disconnect = None

    @property
    def client(self) -> BleClient:
        """Return the BLE client instance."""
        return self.config_entry.runtime_data.client

    def _char(self, fe8f_uuid: str, fccd_uuid: str | None = None) -> str:
        """Return the correct characteristic UUID for the detected protocol."""
        if self._is_fccd and fccd_uuid is not None:
            return fccd_uuid
        return fe8f_uuid

    @property
    def _notify_chars(self) -> set[str]:
        """Return characteristic UUIDs to subscribe to based on protocol."""
        if self._is_fccd:
            chars = {
                CHAR_FCCD_VOLUME,
                CHAR_FCCD_AUDIO_CONTROL,
                CHAR_FCCD_NOW_PLAYING,
                CHAR_FCCD_EQ,
                CHAR_FCCD_SOURCE,
            }
            if FEATURE_ROOM_PLACEMENT in self._fccd_features:
                chars.add(CHAR_FCCD_ROOM_PLACEMENT)
            if FEATURE_NIGHT_MODE in self._fccd_features:
                chars.add(CHAR_FCCD_NIGHT_MODE)
            return chars
        return {
            CHAR_VOLUME,
            CHAR_CONTROL,
            CHAR_MEDIA_INFO,
            CHAR_EQ,
        }

    async def _async_update_data(self) -> MarshallState:
        """Refresh state via BLE reads and notifications."""
        if self._unsub_disconnect is None:
            self._unsub_disconnect = self.client.register_disconnect_callback(
                self._handle_unexpected_disconnect
            )
        try:
            await self.client.async_connect()
            await self._detect_protocol()
            await self._ensure_notifications()
            await self._refresh_dynamic_state()
            if not self._static_loaded:
                await self._refresh_static_state()
                self._static_loaded = True
        except MarshallBleError as exception:
            LOGGER.debug("BLE update failed: %s", exception)
            raise UpdateFailed(exception) from exception

        return self.state

    async def _detect_protocol(self) -> None:
        """Detect whether device uses FCCD (Gen III) or FE8F (Gen II) protocol."""
        if self._notify_started:
            return
        self._is_fccd = False
        try:
            await self.client.async_read(CHAR_FCCD_VOLUME)
            self._is_fccd = True
            self._fccd_features = {
                feature
                for feature, uuid in FCCD_FEATURE_CHARACTERISTICS.items()
                if self.client.has_characteristic(uuid)
            }
            LOGGER.debug(
                "Detected FCCD protocol (Gen III+), features: %s",
                sorted(self._fccd_features),
            )
        except MarshallBleError:
            LOGGER.debug("Using FE8F protocol (Gen II)")

    async def _ensure_notifications(self) -> None:
        if self._notify_started:
            return
        for uuid in self._notify_chars:
            try:
                await self.client.async_start_notify(uuid, self._handle_notify)
            except MarshallBleError as exception:
                LOGGER.debug("BLE notify failed for %s: %s", uuid, exception)
        self._notify_started = True

    async def _refresh_dynamic_state(self) -> None:
        # Volume
        vol_uuid = self._char(CHAR_VOLUME, CHAR_FCCD_VOLUME)
        volume = await self._safe_read(vol_uuid)
        if volume:
            self.state.volume_step = volume[0]

        # Battery (only on FE8F devices)
        if not self._is_fccd:
            battery = await self._safe_read(CHAR_BATTERY_LEVEL)
            if battery:
                self.state.battery_level = battery[0]

        # Control / Audio status
        ctrl_uuid = self._char(CHAR_CONTROL, CHAR_FCCD_AUDIO_CONTROL)
        control = await self._safe_read(ctrl_uuid)
        if self._is_fccd:
            # FCCD: audio control byte represents play/pause state directly
            if control and len(control) >= 1:
                self.state.is_playing = control[0] == 0x01
            # Source
            src_uuid = self._char(CHAR_CONTROL, CHAR_FCCD_SOURCE)
            src_data = await self._safe_read(src_uuid)
            source = self._decode_fccd_source(src_data)
            if source is not None:
                self.state.source = source
            if FEATURE_NIGHT_MODE in self._fccd_features:
                night = await self._safe_read(CHAR_FCCD_NIGHT_MODE)
                if night:
                    self.state.night_mode = night[0] == 0x01
            if FEATURE_ROOM_PLACEMENT in self._fccd_features:
                placement = await self._safe_read(CHAR_FCCD_ROOM_PLACEMENT)
                if placement and placement[0] in ROOM_PLACEMENT_OPTIONS:
                    self.state.room_placement = placement[0]
            now_playing = await self._safe_read(CHAR_FCCD_NOW_PLAYING)
            if now_playing:
                self._apply_media_info(now_playing)
        elif control and len(control) > STATUS_INDEX_INTERACTION_SOUND:
            self.state.source = AUDIO_SOURCE_MAPPING.get(control[STATUS_INDEX_SOURCE])
            status = PLAY_STATUS_MAPPING.get(control[STATUS_INDEX_PLAY_STATUS])
            self.state.is_playing = status == "playing" if status else None
            self.state.interaction_sounds = bool(
                control[STATUS_INDEX_INTERACTION_SOUND]
            )

    async def _refresh_static_state(self) -> None:
        self.state.device_name = self._decode_device_name(
            await self._safe_read(CHAR_DEVICE_NAME)
        )
        self.state.model = self._decode_str(await self._safe_read(CHAR_MODEL_NUMBER))
        self.state.serial = self._decode_str(await self._safe_read(CHAR_SERIAL_NUMBER))
        self.state.firmware = self._decode_str(await self._safe_read_firmware())
        self.state.hardware = self._decode_str(await self._safe_read(CHAR_HARDWARE_REV))

        # Volume range: FCCD devices expose their max step (Acton III: 31)
        if self._is_fccd:
            limit = await self._safe_read(CHAR_FCCD_VOLUME_LIMIT)
            if limit and 0 < limit[0] <= MAX_SANE_VOLUME_STEPS:
                self.state.volume_max = limit[0]
            else:
                self.state.volume_max = FCCD_VOLUME_MAX_DEFAULT
        else:
            self.state.volume_max = VOLUME_MAX

        # LED brightness (FE8F only)
        if not self._is_fccd:
            led_data = await self._safe_read(CHAR_LED_BRIGHTNESS)
            if led_data:
                self.state.led_brightness = led_data[0] - LED_BRIGHTNESS_OFFSET

        # EQ bands
        eq_uuid = self._char(CHAR_EQ, CHAR_FCCD_EQ)
        eq_data = await self._safe_read(eq_uuid)
        if eq_data and len(eq_data) >= EQ_BAND_COUNT:
            self.state.eq_bands = self._decode_eq_bands(eq_data)

    async def _safe_read_firmware(self) -> bytes:
        """Read firmware revision, handling duplicate UUIDs on FCCD devices."""
        try:
            return await self.client.async_read(CHAR_FIRMWARE_REV)
        except MarshallBleError:
            pass
        # On FCCD devices, firmware UUID (2A26) appears in both Device Info
        # and Google Fast Pair services. Read from Device Info service directly.
        try:
            return await self.client.async_read_from_service(
                "0000180a-0000-1000-8000-00805f9b34fb",
                CHAR_FIRMWARE_REV,
            )
        except MarshallBleError:
            return b""

    def _handle_notify(self, uuid: str, data: bytes) -> None:
        vol_uuid = self._char(CHAR_VOLUME, CHAR_FCCD_VOLUME)
        ctrl_uuid = self._char(CHAR_CONTROL, CHAR_FCCD_AUDIO_CONTROL)
        eq_uuid = self._char(CHAR_EQ, CHAR_FCCD_EQ)
        media_uuid = self._char(CHAR_MEDIA_INFO, CHAR_FCCD_NOW_PLAYING)
        src_uuid = self._char(CHAR_CONTROL, CHAR_FCCD_SOURCE)

        if uuid == vol_uuid and data:
            self.state.volume_step = data[0]
        elif uuid == ctrl_uuid:
            if self._is_fccd:
                if data and len(data) >= 1:
                    self.state.is_playing = data[0] == 0x01
            else:
                self.state.control_raw = data
                if data and len(data) > STATUS_INDEX_INTERACTION_SOUND:
                    self.state.source = AUDIO_SOURCE_MAPPING.get(
                        data[STATUS_INDEX_SOURCE]
                    )
                    status = PLAY_STATUS_MAPPING.get(data[STATUS_INDEX_PLAY_STATUS])
                    self.state.is_playing = status == "playing" if status else None
                    self.state.interaction_sounds = bool(
                        data[STATUS_INDEX_INTERACTION_SOUND]
                    )
        elif uuid == media_uuid:
            self._apply_media_info(data)
        elif self._is_fccd and uuid in (CHAR_FCCD_NIGHT_MODE, CHAR_FCCD_ROOM_PLACEMENT):
            self._apply_fccd_setting(uuid, data)
        elif uuid == src_uuid and self._is_fccd:
            source = self._decode_fccd_source(data)
            if source is not None:
                self.state.source = source
        elif uuid == eq_uuid:
            if data and len(data) >= EQ_BAND_COUNT:
                self.state.eq_bands = self._decode_eq_bands(data)
        else:
            self.state.unknown_notify[uuid] = data

        self.async_set_updated_data(self.state)

    def _apply_fccd_setting(self, uuid: str, data: bytes) -> None:
        """Apply a night mode / room placement value."""
        if not data:
            return
        if uuid == CHAR_FCCD_NIGHT_MODE:
            self.state.night_mode = data[0] == 0x01
        elif data[0] in ROOM_PLACEMENT_OPTIONS:
            self.state.room_placement = data[0]

    @staticmethod
    def _decode_eq_bands(data: bytes) -> list[int | None]:
        """Decode EQ bands; 0xFF marks a band the device does not have."""
        return [
            None if b == EQ_BAND_UNUSED else min(b, EQ_BAND_MAX_VALUE)
            for b in data[:EQ_BAND_COUNT]
        ]

    def _apply_media_info(self, data: bytes) -> None:
        """Update title/artist/album from a media info payload."""
        if data == b"\x00\x00\x00\xff\x00\x00\x00\x00" or data.startswith(
            b"\x00\x00\x00\xff"
        ):
            return
        entries = self._parse_media_entries(data)
        self.state.media_title = entries.get(MEDIA_ENTRY_TITLE)
        self.state.media_artist = entries.get(MEDIA_ENTRY_ARTIST)
        self.state.media_album = entries.get(MEDIA_ENTRY_ALBUM)
        self.state.media_info = self._decode_media_info(data)

    @staticmethod
    def _parse_media_entries(data: bytes) -> dict[int, str]:
        """
        Parse media info entries: [id u32][type u16][len u16][utf-8 bytes]...

        Mirrors the Marshall app: optional '[' / ']' framing is stripped and
        "not provided" placeholders are dropped.
        """
        if data[:1] == b"[":
            data = data[1:]
        if data[-1:] == b"]":
            data = data[:-1]
        entries: dict[int, str] = {}
        offset = 0
        while offset + MEDIA_INFO_HEADER_SIZE <= len(data):
            entry_id = int.from_bytes(data[offset : offset + 4], "big")
            length = int.from_bytes(data[offset + 6 : offset + 8], "big")
            offset += MEDIA_INFO_HEADER_SIZE
            if entry_id in {0, MEDIA_INFO_ENTRY_MARKER_TERMINATOR}:
                break
            if length > MEDIA_INFO_MAX_STRING_LENGTH or offset + length > len(data):
                break
            text = data[offset : offset + length].decode("utf-8", errors="ignore")
            text = text.strip("\x00").strip()
            offset += length
            if text and text.lower() not in MEDIA_NOT_PROVIDED:
                entries.setdefault(entry_id, text)
        return entries

    @staticmethod
    def _decode_fccd_source(data: bytes) -> str | None:
        """Decode an FCCD audio source payload (single byte or scheme 2)."""
        if not data:
            return None
        value = data[0]
        if value == FCCD_SOURCE_SCHEME2_MARKER:
            if len(data) < FCCD_SOURCE_SCHEME2_MIN_LENGTH:
                return None
            value = data[FCCD_SOURCE_SCHEME2_INDEX]
        return FCCD_AUDIO_SOURCE_MAPPING.get(value, f"0x{value:02X}")

    async def _safe_read(self, uuid: str) -> bytes:
        try:
            return await self.client.async_read(uuid)
        except MarshallBleError as exception:
            LOGGER.debug("BLE read failed for %s: %s", uuid, exception)
            return b""

    async def async_set_led_brightness(self, brightness: int) -> None:
        """Set LED brightness (0-35). FE8F only."""
        if self._is_fccd:
            LOGGER.debug("LED brightness not supported on FCCD devices")
            return
        raw_value = brightness + LED_BRIGHTNESS_OFFSET
        try:
            await self.client.async_write(
                CHAR_LED_BRIGHTNESS, bytes([raw_value]), response=True
            )
            self.state.led_brightness = brightness
            self.async_set_updated_data(self.state)
        except MarshallBleError as exception:
            LOGGER.debug("Failed to set LED brightness: %s", exception)

    async def async_set_audio_source(self, source: str) -> None:
        """Set audio source (Bluetooth, Aux, or RCA)."""
        if self._is_fccd:
            if source not in FCCD_AUDIO_SOURCE_COMMANDS:
                LOGGER.warning("Invalid audio source for FCCD device: %s", source)
                return
            command = FCCD_AUDIO_SOURCE_COMMANDS[source]
            try:
                await self.client.async_write(
                    CHAR_FCCD_SOURCE, bytes([command]), response=True
                )
                self.state.source = source
                self.async_set_updated_data(self.state)
            except MarshallBleError as exception:
                LOGGER.debug("Failed to set audio source: %s", exception)
            return

        if source not in AUDIO_SOURCE_COMMANDS:
            LOGGER.warning("Invalid audio source: %s", source)
            return
        command = AUDIO_SOURCE_COMMANDS[source]
        try:
            await self.client.async_write(CHAR_CONTROL, bytes([command]), response=True)
            self.state.source = source
            self.async_set_updated_data(self.state)
        except MarshallBleError as exception:
            LOGGER.debug("Failed to set audio source: %s", exception)

    async def async_set_volume_step(self, step: int) -> None:
        """Set the raw volume step (0..volume_max)."""
        step = max(0, min(self.state.volume_max, step))
        uuid = self._char(CHAR_VOLUME, CHAR_FCCD_VOLUME)
        try:
            await self.client.async_write(uuid, bytes([step]), response=True)
        except MarshallBleError as exception:
            LOGGER.debug("Failed to set volume: %s", exception)
            return
        self.state.volume_step = step
        self.async_set_updated_data(self.state)

    async def async_set_night_mode(self, *, enabled: bool) -> None:
        """Enable or disable night mode (FCCD)."""
        try:
            await self.client.async_write(
                CHAR_FCCD_NIGHT_MODE, bytes([0x01 if enabled else 0x00]), response=True
            )
        except MarshallBleError as exception:
            LOGGER.error("Failed to set night mode: %s", exception)
            return
        self.state.night_mode = enabled
        self.async_set_updated_data(self.state)

    async def async_set_room_placement(self, value: int) -> None:
        """Set placement compensation (FCCD)."""
        if value not in ROOM_PLACEMENT_OPTIONS:
            LOGGER.warning("Invalid room placement: %s", value)
            return
        try:
            await self.client.async_write(
                CHAR_FCCD_ROOM_PLACEMENT, bytes([value]), response=True
            )
        except MarshallBleError as exception:
            LOGGER.error("Failed to set room placement: %s", exception)
            return
        self.state.room_placement = value
        self.async_set_updated_data(self.state)

    async def async_set_interaction_sounds(self, *, enabled: bool) -> None:
        """Enable or disable interaction sounds. FE8F only."""
        if self._is_fccd:
            LOGGER.debug("Interaction sounds not supported on FCCD devices")
            return
        try:
            command = 0x01 if enabled else 0x00
            await self.client.async_write(CHAR_CONTROL, bytes([command]), response=True)
            self.state.interaction_sounds = enabled
            self.async_set_updated_data(self.state)
            LOGGER.info("Set interaction sounds to: %s", enabled)
        except MarshallBleError as exception:
            LOGGER.debug("Failed to set interaction sounds: %s", exception)

    async def async_enter_pairing_mode(self) -> None:
        """Request the speaker to enter Bluetooth pairing mode."""
        pairing_uuid = self._char(CHAR_PAIRING, CHAR_FCCD_PAIRING)
        try:
            await self.client.async_write(pairing_uuid, bytes([0x01]), response=True)
            LOGGER.info("Requested speaker to enter pairing mode")
        except MarshallBleError as exception:
            LOGGER.error("Failed to enter pairing mode: %s", exception)
            raise

    async def async_set_device_name(self, name: str) -> None:
        """Set the device name on the speaker."""
        if not name:
            LOGGER.warning("Device name cannot be empty")
            return

        name_bytes = name.encode("utf-8")
        name_length = len(name_bytes)

        if self._is_fccd:
            # FCCD rename takes the raw UTF-8 name (Marshall app RENAME wrapper)
            try:
                await self.client.async_write(
                    CHAR_FCCD_RENAME,
                    name_bytes[:DEVICE_NAME_MAX_LENGTH],
                    response=True,
                )
            except MarshallBleError as exception:
                LOGGER.error("Failed to set device name: %s", exception)
                raise
            self.state.device_name = name
            self.async_set_updated_data(self.state)
            LOGGER.info("Set device name to: %s", name)
            return

        if name_length > DEVICE_NAME_MAX_LENGTH:
            LOGGER.warning(
                "Device name too long (max %d bytes), truncating",
                DEVICE_NAME_MAX_LENGTH,
            )
            name_bytes = name_bytes[:DEVICE_NAME_MAX_LENGTH]
            name_length = DEVICE_NAME_MAX_LENGTH

        data = bytes([0x01, name_length]) + name_bytes

        try:
            await self.client.async_write(CHAR_DEVICE_NAME, data, response=True)

            device_name_data = await self._safe_read(CHAR_DEVICE_NAME)
            if device_name_data:
                self.state.device_name = self._decode_device_name(device_name_data)
            else:
                self.state.device_name = name

            self.async_set_updated_data(self.state)
            LOGGER.info("Set device name to: %s", name)
        except MarshallBleError as exception:
            LOGGER.error("Failed to set device name: %s", exception)
            raise

    async def async_set_equaliser_band(self, index: int, value: int) -> None:
        """Set a single EQ band, keeping the others unchanged."""
        bands = [5 if b is None else b for b in self.state.eq_bands]
        bands[index] = value
        await self.async_set_equaliser_profile(bands)

    async def async_set_equaliser_profile(self, bands: list[int]) -> None:
        """
        Set the equaliser profile with 5 bands (0-10, where 5 is neutral).

        Bands the device does not have (reported as 0xFF) are written back as
        0xFF regardless of the requested value.
        """
        if not bands or len(bands) != EQ_BAND_COUNT:
            LOGGER.warning(
                "Invalid EQ bands (expected %d values, got %d)",
                EQ_BAND_COUNT,
                len(bands) if bands else 0,
            )
            return

        validated_bands = []
        for i, value in enumerate(bands):
            if not isinstance(value, int) or value < 0 or value > EQ_BAND_MAX_VALUE:
                LOGGER.warning(
                    "Invalid EQ band %d value: %s (must be 0-%d)",
                    i,
                    value,
                    EQ_BAND_MAX_VALUE,
                )
                return
            validated_bands.append(value)

        current = self.state.eq_bands
        new_bands: list[int | None] = [
            None if i < len(current) and current[i] is None else value
            for i, value in enumerate(validated_bands)
        ]
        data = bytes(EQ_BAND_UNUSED if b is None else b for b in new_bands)
        eq_uuid = self._char(CHAR_EQ, CHAR_FCCD_EQ)

        try:
            await self.client.async_write(eq_uuid, data, response=True)
            self.state.eq_bands = new_bands
            self.async_set_updated_data(self.state)
            LOGGER.info("Set EQ bands to: %s", validated_bands)
        except MarshallBleError as exception:
            LOGGER.error("Failed to set EQ profile: %s", exception)
            raise

    @staticmethod
    def _decode_str(data: bytes) -> str | None:
        if not data:
            return None
        try:
            return data.decode(errors="ignore").strip("\x00").strip()
        except UnicodeDecodeError:
            return None

    @staticmethod
    def _decode_device_name(data: bytes) -> str | None:
        if not data:
            return None
        if data[0] != 0x01:
            return MarshallDataUpdateCoordinator._decode_str(data)
        if len(data) < MIN_DEVICE_NAME_DATA_LENGTH:
            return None
        length = data[1]
        if length == 0:
            return ""
        start = 2
        end = min(len(data), start + length)
        return MarshallDataUpdateCoordinator._decode_str(data[start:end])

    @staticmethod
    def _decode_media_info(data: bytes) -> str | None:
        if not data or len(data) < MEDIA_INFO_HEADER_SIZE:
            return None

        if data == b"\x00\x00\x00\xff\x00\x00\x00\x00" or data.startswith(
            b"\x00\x00\x00\xff"
        ):
            return None

        parts = []
        offset = 0

        try:
            while offset < len(data):
                if offset + MEDIA_INFO_HEADER_SIZE > len(data):
                    break

                marker = int.from_bytes(data[offset : offset + 4], "big")
                offset += 4

                if marker in {MEDIA_INFO_ENTRY_MARKER_TERMINATOR, 0}:
                    break

                offset += 2

                str_length = int.from_bytes(data[offset : offset + 2], "big")
                offset += 2

                if (
                    str_length == 0
                    or str_length > MEDIA_INFO_MAX_STRING_LENGTH
                    or offset + str_length > len(data)
                ):
                    break

                string_data = data[offset : offset + str_length]
                decoded = MarshallDataUpdateCoordinator._decode_str(string_data)

                if decoded:
                    parts.append(decoded)

                offset += str_length
        except (IndexError, ValueError, OverflowError):
            pass

        if len(parts) >= MEDIA_INFO_MIN_PARTS_FOR_FULL_FORMAT:
            return f"{parts[0]} - {parts[1]} ({parts[2]})"
        if parts:
            return " - ".join(parts)

        if data and data != b"\x00" * len(data):
            return data.hex()

        return None
