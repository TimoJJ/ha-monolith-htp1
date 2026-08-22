"""The Monoprice HTP-1 integration."""
from __future__ import annotations

import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .aiohtp1 import Htp1
from .const import DOMAIN

PLATFORMS = ["sensor", "number", "switch", "select", "button", "media_player"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    htp1 = Htp1(entry.data["host"], session)

    try:
        # Ensure websocket + initial state are ready during setup.
        await asyncio.wait_for(htp1.connect(), timeout=10)

        # Store instance only after a successful connection.
        hass.data[DOMAIN][entry.entry_id] = htp1

        async def _shutdown(event):
            await htp1.stop()

        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)
        )

        # Forward platforms; if this fails, we must clean up.
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        return True

    except Exception as err:
        # Roll back any partial setup cleanly.
        try:
            hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        except Exception:
            pass

        await htp1.stop()
        raise ConfigEntryNotReady(f"HTP-1 not ready: {err}") from err


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    htp1 = hass.data[DOMAIN].pop(entry.entry_id)
    await htp1.stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
