"""Custom integration to control Marshall Bluetooth speakers over BLE."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.loader import async_get_loaded_integration

from .ble import MarshallBleClient, MarshallBleError
from .const import (
    CONF_ADDRESS,
    CONF_NAME,
    DOMAIN,
    LOGGER,
    SERVICE_ENTER_PAIRING_MODE,
    SERVICE_SET_DEVICE_NAME,
)
from .coordinator import MarshallDataUpdateCoordinator
from .data import MarshallData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import MarshallConfigEntry

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
]


async def _async_handle_enter_pairing_mode(hass: HomeAssistant, call: Any) -> None:
    """Handle the enter_pairing_mode service call."""
    device_id = call.data["device_id"]
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)

    if device is None:
        LOGGER.error("Device not found: %s", device_id)
        return

    # Find the config entry for this device
    config_entry = None
    for entry_id in device.config_entries:
        if (
            temp_entry := hass.config_entries.async_get_entry(entry_id)
        ) and temp_entry.domain == DOMAIN:
            config_entry = temp_entry
            break

    if config_entry is None:
        LOGGER.error("No config entry found for device: %s", device_id)
        return

    coordinator = config_entry.runtime_data.coordinator
    try:
        await coordinator.async_enter_pairing_mode()
    except MarshallBleError as exception:
        LOGGER.error("Failed to enter pairing mode: %s", exception)


async def _async_handle_set_device_name(hass: HomeAssistant, call: Any) -> None:
    """Handle the set_device_name service call."""
    device_id = call.data["device_id"]
    name = call.data["name"]
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)

    if device is None:
        LOGGER.error("Device not found: %s", device_id)
        return

    # Find the config entry for this device
    config_entry = None
    for entry_id in device.config_entries:
        if (
            temp_entry := hass.config_entries.async_get_entry(entry_id)
        ) and temp_entry.domain == DOMAIN:
            config_entry = temp_entry
            break

    if config_entry is None:
        LOGGER.error("No config entry found for device: %s", device_id)
        return

    coordinator = config_entry.runtime_data.coordinator
    try:
        await coordinator.async_set_device_name(name)

        # Update device registry with the new name for immediate UI update
        device_registry.async_update_device(
            device_id,
            name_by_user=name,
        )
        LOGGER.info("Updated device name in registry to: %s", name)
    except MarshallBleError as exception:
        LOGGER.error("Failed to set device name: %s", exception)


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: MarshallConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    coordinator = MarshallDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=DOMAIN,
    )
    coordinator.config_entry = entry
    entry.runtime_data = MarshallData(
        client=MarshallBleClient(
            hass=hass,
            address=entry.data[CONF_ADDRESS],
            name=entry.data.get(CONF_NAME) or entry.title,
        ),
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Register device services
    hass.services.async_register(
        DOMAIN,
        SERVICE_ENTER_PAIRING_MODE,
        lambda call: _async_handle_enter_pairing_mode(hass, call),
        schema=vol.Schema({vol.Required("device_id"): cv.string}),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_DEVICE_NAME,
        lambda call: _async_handle_set_device_name(hass, call),
        schema=vol.Schema(
            {
                vol.Required("device_id"): cv.string,
                vol.Required("name"): cv.string,
            }
        ),
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: MarshallConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.async_disconnect()
    return unload_ok


async def async_reload_entry(
    hass: HomeAssistant,
    entry: MarshallConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
