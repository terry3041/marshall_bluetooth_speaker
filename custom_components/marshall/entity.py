"""Base entity for Marshall speakers."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import MarshallDataUpdateCoordinator


class MarshallEntity(CoordinatorEntity[MarshallDataUpdateCoordinator]):
    """Marshall speakers base entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MarshallDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._address = coordinator.config_entry.data.get("address")

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about the Marshall speaker."""
        name = (
            self.coordinator.state.device_name
            or self.coordinator.config_entry.title
            or NAME
        )
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            connections={(CONNECTION_BLUETOOTH, self._address)}
            if self._address
            else set(),
            manufacturer="Marshall",
            model=self.coordinator.state.model,
            name=name,
            sw_version=self.coordinator.state.firmware,
            hw_version=self.coordinator.state.hardware,
        )
