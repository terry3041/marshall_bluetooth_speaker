"""Custom types for Marshall speakers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .ble import MarshallBleClient
    from .coordinator import MarshallDataUpdateCoordinator


type MarshallConfigEntry = ConfigEntry[MarshallData]


@dataclass
class MarshallState:
    """Runtime state for Marshall speakers."""

    volume_step: int | None = None
    battery_level: int | None = None
    is_playing: bool | None = None
    source: str | None = None
    interaction_sounds: bool | None = None
    media_info: str | None = None
    device_name: str | None = None
    model: str | None = None
    serial: str | None = None
    firmware: str | None = None
    hardware: str | None = None
    control_raw: bytes | None = None
    eq_raw: bytes | None = None
    eq_bands: list[int] = field(
        default_factory=lambda: [5, 5, 5, 5, 5]
    )  # 5 bands, default neutral (5)
    led_brightness: int | None = None
    unknown_notify: dict[str, bytes] = field(default_factory=dict)


@dataclass
class MarshallData:
    """Data for the Marshall speakers integration."""

    client: MarshallBleClient
    coordinator: MarshallDataUpdateCoordinator
    integration: Integration
