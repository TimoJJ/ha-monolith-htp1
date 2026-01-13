"""The Monoprice HTP-1 integration."""
from __future__ import annotations

import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.core import HomeAssistant
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .aiohtp1 import Htp1

PLATFORMS = ["sensor", "number", "switch", "select", "media_player"]
# PLATFORMS = ["sensor", "number", "switch", "select"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    htp1 = Htp1(entry.data["host"], session)

    # store instance
    hass.data[DOMAIN][entry.entry_id] = htp1

    # IMPORTANT: establish websocket connection during setup
    # If the device is not reachable yet, ask Home Assistant to retry.
    try:
        await htp1.try_connect()
    except Exception as err:
        # cleanup and let HA retry later automatically
        await htp1.stop()
        raise ConfigEntryNotReady(f"HTP-1 websocket connect failed: {err}") from err

    async def _shutdown(event):
        await htp1.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True



async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    htp1 = hass.data[DOMAIN].pop(entry.entry_id)
    await htp1.stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
