"""Custom integration to control Marshall Bluetooth speakers over BLE."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.loader import async_get_loaded_integration

from .ble import ActonBleClient
from .const import CONF_ADDRESS, CONF_NAME, DOMAIN, LOGGER
from .coordinator import ActonDataUpdateCoordinator
from .data import ActonData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import ActonConfigEntry

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ActonConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    coordinator = ActonDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=DOMAIN,
    )
    coordinator.config_entry = entry
    entry.runtime_data = ActonData(
        client=ActonBleClient(
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

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ActonConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.async_disconnect()
    return unload_ok


async def async_reload_entry(
    hass: HomeAssistant,
    entry: ActonConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
