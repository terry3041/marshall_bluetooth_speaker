"""Adds config flow for Marshall speakers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.helpers import selector

if TYPE_CHECKING:
    from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from .const import CONF_ADDRESS, CONF_NAME, DOMAIN, FCCD_SERVICE_UUID, FE8F_SERVICE_UUID

SHORT_UUID_LENGTH = 4


class MarshallFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Marshall speakers."""

    VERSION = 1
    _discovered_address: str | None = None
    _discovered_name: str | None = None

    async def async_step_bluetooth(
        self,
        discovery_info: BluetoothServiceInfoBleak | dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by bluetooth discovery."""
        user_input: dict | None = None
        if isinstance(discovery_info, dict):
            user_input = discovery_info
            discovery_info = None

        if discovery_info is not None:
            if not self._is_marshall_device(
                discovery_info.name,
                discovery_info.service_uuids,
                discovery_info.service_data,
            ):
                return self.async_abort(reason="not_supported")

            self._discovered_address = discovery_info.address
            self._discovered_name = discovery_info.name or "Marshall Speaker"

        if self._discovered_address is None:
            return self.async_abort(reason="not_supported")

        await self.async_set_unique_id(self._discovered_address)
        self._abort_if_unique_id_configured()

        if user_input is None:
            return self.async_show_form(
                step_id="bluetooth",
                data_schema=vol.Schema(
                    {
                        vol.Optional(
                            CONF_NAME, default=self._discovered_name
                        ): selector.TextSelector(
                            selector.TextSelectorConfig(
                                type=selector.TextSelectorType.TEXT,
                            ),
                        ),
                    },
                ),
                description_placeholders={"address": self._discovered_address},
                errors={},
            )

        name = user_input.get(CONF_NAME) or self._discovered_name or "Marshall Speaker"
        return self.async_create_entry(
            title=name,
            data={CONF_ADDRESS: self._discovered_address, CONF_NAME: name},
        )

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            name = user_input.get(CONF_NAME)
            if not name:
                discovered = await self._async_get_discovered()
                name = discovered.get(address) or address
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=name,
                data={CONF_ADDRESS: address, CONF_NAME: name},
            )

        discovered = await self._async_get_discovered()
        if discovered:
            first_address = next(iter(discovered.keys()))
            default_name = discovered[first_address]
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_ADDRESS, default=first_address
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=list(discovered.keys()),
                            ),
                        ),
                        vol.Optional(
                            CONF_NAME, default=default_name
                        ): selector.TextSelector(
                            selector.TextSelectorConfig(
                                type=selector.TextSelectorType.TEXT,
                            ),
                        ),
                    },
                ),
                errors={},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Optional(CONF_NAME): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                },
            ),
            errors={},
        )

    @staticmethod
    def _short_service_uuids(service_uuids: list[str]) -> set[str]:
        short_uuids: set[str] = set()
        for uuid in service_uuids:
            normalized = uuid.upper()
            if len(normalized) == SHORT_UUID_LENGTH:
                short_uuids.add(normalized)
            elif (
                normalized.startswith("0000")
                and "-0000-1000-8000-00805F9B34FB" in normalized
            ):
                short_uuids.add(normalized[SHORT_UUID_LENGTH : SHORT_UUID_LENGTH * 2])
        return short_uuids

    @classmethod
    def _supports_service(
        cls,
        service_uuids: list[str],
        service_data: dict[str, bytes] | None = None,
    ) -> bool:
        short_uuids = cls._short_service_uuids(service_uuids)
        if service_data:
            short_uuids.update(cls._short_service_uuids(list(service_data.keys())))
        return FE8F_SERVICE_UUID in short_uuids or FCCD_SERVICE_UUID in short_uuids

    @classmethod
    def _is_marshall_device(
        cls,
        name: str | None,
        service_uuids: list[str],
        service_data: dict[str, bytes] | None = None,
    ) -> bool:
        """Check if device is a Marshall speaker by service UUID or name."""
        if cls._supports_service(service_uuids, service_data):
            return True
        if name:
            upper = name.upper()
            for prefix in ("ACTON", "STANMORE", "WOBURN", "MARSHALL",
                           "WILLEN", "MIDDLETON", "KILBURN", "EMBERTON",
                           "STOCKWELL", "TURNER", "BROMLEY"):
                if prefix in upper:
                    return True
        return False

    async def _async_get_discovered(self) -> dict[str, str]:
        discovered: dict[str, str] = {}
        for service_info in bluetooth.async_discovered_service_info(self.hass):
            if not self._is_marshall_device(
                service_info.name,
                service_info.service_uuids,
                service_info.service_data,
            ):
                continue
            address = service_info.address
            name = service_info.name or "Marshall Speaker"
            discovered[address] = name
        return discovered
