"""Config flow for Monoprice HTP-1 integration."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow as _ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .aiohtp1 import AioHtp1Exception, ConnectionException, Htp1
from .const import DOMAIN, LOGGER
from .helpers import async_get_clientsession


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> str:
    """Validate the user input allows us to connect and fetch a stable unique id."""
    session = async_get_clientsession(hass)
    htp1 = Htp1(host=data[CONF_HOST], session=session)

    try:
        # Ensure validation cannot hang indefinitely.
        await asyncio.wait_for(htp1.connect(), timeout=10)
        serial_number = htp1.serial_number
        return serial_number
    finally:
        # Always stop/cleanup even if connect or reading serial fails.
        await htp1.stop()


class ConfigFlow(_ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Monoprice HTP-1."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
        host_default: str | None = None,
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                serial_number = await validate_input(self.hass, user_input)
            except (asyncio.TimeoutError, ConnectionException):
                errors["base"] = "cannot_connect"
            except AioHtp1Exception:
                LOGGER.debug("Validation failed with AioHtp1Exception", exc_info=True)
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured()

                host = user_input[CONF_HOST]
                title = f"HTP-1 ({host})"
                return self.async_create_entry(title=title, data=user_input)

        step_id = "reconfigure" if host_default else "user"
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=host_default): str,
            }
        )

        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)

    async def async_step_reconfigure(
        self,
        user_input: Mapping[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle a reconfiguration of the config entry."""
        reconfigure_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        host_default = (
            reconfigure_entry.data[CONF_HOST] if reconfigure_entry is not None else None
        )
        if user_input is not None:
            host_default = user_input.get(CONF_HOST, host_default)

        return await self.async_step_user(
            user_input=dict(user_input) if user_input is not None else None,
            host_default=host_default,
        )
