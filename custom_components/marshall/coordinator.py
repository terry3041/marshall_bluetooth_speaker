"""DataUpdateCoordinator for Marshall Bluetooth speakers."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

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
    CHAR_FCCD_NOW_PLAYING,
    CHAR_FCCD_PAIRING,
    CHAR_FCCD_SOURCE,
    CHAR_FCCD_VOLUME,
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
    LED_BRIGHTNESS_OFFSET,
    LOGGER,
    MEDIA_INFO_ENTRY_MARKER_TERMINATOR,
    MEDIA_INFO_HEADER_SIZE,
    MEDIA_INFO_MAX_STRING_LENGTH,
    MEDIA_INFO_MIN_PARTS_FOR_FULL_FORMAT,
    PLAY_STATUS_MAPPING,
    STATUS_INDEX_INTERACTION_SOUND,
    STATUS_INDEX_PLAY_STATUS,
    STATUS_INDEX_SOURCE,
)
from .data import MarshallState

MIN_DEVICE_NAME_DATA_LENGTH = 2
EQ_BAND_MAX_VALUE = 10
# 0xFF means "unused/neutral" for FCCD EQ bands
EQ_BAND_UNUSED = 0xFF

if TYPE_CHECKING:
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
        self._is_fccd = False  # True for Gen III+ (FCCD protocol), False for Gen II (FE8F)

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
            return {
                CHAR_FCCD_VOLUME,
                CHAR_FCCD_AUDIO_CONTROL,
                CHAR_FCCD_NOW_PLAYING,
                CHAR_FCCD_EQ,
                CHAR_FCCD_SOURCE,
            }
        return {
            CHAR_VOLUME,
            CHAR_CONTROL,
            CHAR_MEDIA_INFO,
            CHAR_EQ,
        }

    async def _async_update_data(self) -> MarshallState:
        """Refresh state via BLE reads and notifications."""
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
            LOGGER.debug("Detected FCCD protocol (Gen III+)")
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
            if src_data and len(src_data) >= 1:
                self.state.source = {0x00: "Bluetooth", 0x01: "Aux"}.get(
                    src_data[0], f"0x{src_data[0]:02X}"
                )
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

        # LED brightness (FE8F only)
        if not self._is_fccd:
            led_data = await self._safe_read(CHAR_LED_BRIGHTNESS)
            if led_data:
                self.state.led_brightness = led_data[0] - LED_BRIGHTNESS_OFFSET

        # EQ bands
        eq_uuid = self._char(CHAR_EQ, CHAR_FCCD_EQ)
        eq_data = await self._safe_read(eq_uuid)
        if eq_data and len(eq_data) >= EQ_BAND_COUNT:
            bands = []
            for b in eq_data[:EQ_BAND_COUNT]:
                bands.append(b if b != EQ_BAND_UNUSED else EQ_BAND_MAX_VALUE // 2)
            self.state.eq_bands = bands

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
                    self.state.source = AUDIO_SOURCE_MAPPING.get(data[STATUS_INDEX_SOURCE])
                    status = PLAY_STATUS_MAPPING.get(data[STATUS_INDEX_PLAY_STATUS])
                    self.state.is_playing = status == "playing" if status else None
                    self.state.interaction_sounds = bool(
                        data[STATUS_INDEX_INTERACTION_SOUND]
                    )
        elif uuid == media_uuid:
            if not (
                data == b"\x00\x00\x00\xff\x00\x00\x00\x00"
                or data.startswith(b"\x00\x00\x00\xff")
            ):
                self.state.media_info = self._decode_media_info(data)
        elif uuid == src_uuid and self._is_fccd:
            if data and len(data) >= 1:
                self.state.source = {0x00: "Bluetooth", 0x01: "Aux"}.get(
                    data[0], f"0x{data[0]:02X}"
                )
        elif uuid == eq_uuid:
            if data and len(data) >= EQ_BAND_COUNT:
                bands = []
                for b in data[:EQ_BAND_COUNT]:
                    bands.append(b if b != EQ_BAND_UNUSED else EQ_BAND_MAX_VALUE // 2)
                self.state.eq_bands = bands
        else:
            self.state.unknown_notify[uuid] = data

        self.async_set_updated_data(self.state)

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
            fccd_sources = {"Bluetooth": 0x00, "Aux": 0x01}
            if source not in fccd_sources:
                LOGGER.warning("Invalid audio source for FCCD device: %s", source)
                return
            command = fccd_sources[source]
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

    async def async_set_equaliser_profile(self, bands: list[int]) -> None:
        """Set the equaliser profile with 5 bands (0-10, where 5 is neutral)."""
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

        data = bytes(validated_bands)
        eq_uuid = self._char(CHAR_EQ, CHAR_FCCD_EQ)

        try:
            await self.client.async_write(eq_uuid, data, response=True)
            self.state.eq_bands = validated_bands
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
