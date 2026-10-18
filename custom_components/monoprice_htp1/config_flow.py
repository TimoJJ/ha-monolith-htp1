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

    async def _async_connect(
        self, host: str, errors: dict[str, str]
    ) -> str | None:
        """Connect to the unit and return its serial number; set errors on failure."""
        try:
            return await validate_input(self.hass, {CONF_HOST: host})
        except (asyncio.TimeoutError, ConnectionException):
            errors["base"] = "cannot_connect"
        except AioHtp1Exception:
            LOGGER.debug("Validation failed with AioHtp1Exception", exc_info=True)
            errors["base"] = "unknown"
        return None

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            serial_number = await self._async_connect(host, errors)
            if not errors:
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=f"HTP-1 ({host})", data=user_input)

        schema = vol.Schema({vol.Required(CONF_HOST): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(
        self,
        user_input: Mapping[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Change the host of an existing entry; it must be the same unit."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            serial_number = await self._async_connect(host, errors)
            if not errors:
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_mismatch(reason="wrong_device")

                return self.async_update_reload_and_abort(
                    entry,
                    title=f"HTP-1 ({host})",
                    data_updates={CONF_HOST: host},
                )

        current_host = (user_input or entry.data).get(CONF_HOST)
        schema = vol.Schema({vol.Required(CONF_HOST, default=current_host): str})
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )
