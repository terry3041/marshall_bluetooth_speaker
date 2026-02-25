"""BLE client for Marshall speakers."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from bleak import BleakClient
from bleak.exc import BleakCharacteristicNotFoundError, BleakError
from bleak_retry_connector import establish_connection
from homeassistant.components import bluetooth

from .const import LOGGER

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant


class MarshallBleError(Exception):
    """Base error for BLE operations."""


class MarshallBleClient:
    """Minimal BLE client wrapper for Marshall speakers."""

    def __init__(self, hass: HomeAssistant, address: str, name: str) -> None:
        """
        Initialize the Marshall BLE client.

        Args:
            hass: The Home Assistant instance.
            address: The BLE device address.
            name: The device name.

        """
        self._hass = hass
        self.address = address
        self.name = name
        self._client: BleakClient | None = None
        self._notifying: set[str] = set()
        self._services_loaded = False

    @property
    def is_connected(self) -> bool:
        """Return whether the BLE client is connected."""
        return bool(self._client and self._client.is_connected)

    async def async_connect(self) -> None:
        """Connect to the BLE device."""
        if self.is_connected:
            return

        device = bluetooth.async_ble_device_from_address(
            self._hass,
            self.address,
            connectable=True,
        )
        if device is None:
            msg = "Device not found for address"
            raise MarshallBleError(msg)

        try:
            self._client = await establish_connection(
                BleakClient,
                device,
                name=self.name,
                max_attempts=3,
                logger=LOGGER,
            )
        except BleakError as exc:
            msg = "Failed to connect"
            raise MarshallBleError(msg) from exc

    async def async_disconnect(self) -> None:
        """Disconnect from the BLE device."""
        if not self._client:
            return
        if self._client.is_connected:
            for uuid in list(self._notifying):
                with contextlib.suppress(BleakError):
                    await self._client.stop_notify(uuid)
            with contextlib.suppress(BleakError):
                await self._client.disconnect()
        self._client = None
        self._notifying.clear()
        self._services_loaded = False

    def _has_characteristic(self, uuid: str) -> bool:
        if not self._client or self._client.services is None:
            return False
        return self._client.services.get_characteristic(uuid) is not None

    async def _start_notify_with_characteristic(
        self, uuid: str, notify: Callable[[object, bytearray], None]
    ) -> None:
        if not self._has_characteristic(uuid):
            msg = "Characteristic not found"
            raise MarshallBleError(msg)
        if not self._client:
            msg = "Client unavailable"
            raise MarshallBleError(msg)
        await self._client.start_notify(uuid, notify)

    async def async_start_notify(
        self,
        uuid: str,
        callback: Callable[[str, bytes], None],
    ) -> None:
        """Start notification on a characteristic."""
        await self.async_connect()
        if not self._client:
            msg = "Client unavailable"
            raise MarshallBleError(msg)

        if uuid in self._notifying:
            return

        def _notify(_: object, data: bytearray) -> None:
            callback(uuid, bytes(data))

        try:
            await self._start_notify_with_characteristic(uuid, _notify)
        except BleakCharacteristicNotFoundError:
            self._services_loaded = False
            try:
                await self._start_notify_with_characteristic(uuid, _notify)
            except BleakError as exc:
                msg = "Failed to start notification"
                raise MarshallBleError(msg) from exc
            except MarshallBleError as exc:
                LOGGER.debug("Notify unavailable for %s: %s", uuid, exc)
                raise
        except BleakError as exc:
            LOGGER.debug("Notify error for %s: %s", uuid, exc)
            msg = "Failed to start notification"
            raise MarshallBleError(msg) from exc
        self._notifying.add(uuid)

    async def async_read(self, uuid: str) -> bytes:
        """Read a characteristic."""
        await self.async_connect()
        if not self._client:
            msg = "Client unavailable"
            raise MarshallBleError(msg)
        try:
            return bytes(await self._client.read_gatt_char(uuid))
        except BleakCharacteristicNotFoundError:
            self._services_loaded = False
            try:
                return bytes(await self._client.read_gatt_char(uuid))
            except BleakError as exc:
                msg = "Failed to read characteristic"
                raise MarshallBleError(msg) from exc
        except BleakError as exc:
            msg = "Failed to read characteristic"
            raise MarshallBleError(msg) from exc

    async def async_write(
        self, uuid: str, data: bytes, *, response: bool = False
    ) -> None:
        """Write to a characteristic."""
        await self.async_connect()
        if not self._client:
            msg = "Client unavailable"
            raise MarshallBleError(msg)
        try:
            await self._client.write_gatt_char(uuid, data, response=response)
        except BleakCharacteristicNotFoundError:
            self._services_loaded = False
            try:
                await self._client.write_gatt_char(uuid, data, response=response)
            except BleakError as exc:
                msg = "Failed to write characteristic"
                raise MarshallBleError(msg) from exc
        except BleakError as exc:
            msg = "Failed to write characteristic"
            raise MarshallBleError(msg) from exc


# Alias for backward compatibility
BleClient = MarshallBleClient
