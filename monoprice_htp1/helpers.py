"""Helpers for the Monoprice HTP-1 component."""

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

# Conservative timeouts for LAN devices.
CLIENT_TIMEOUT = aiohttp.ClientTimeout(
    total=30,
    connect=10,
    sock_connect=10,
    sock_read=10,
)


def async_get_clientsession(hass: HomeAssistant) -> aiohttp.ClientSession:
    """Return a HA-managed aiohttp ClientSession with custom timeouts."""
    return async_create_clientsession(hass, timeout=CLIENT_TIMEOUT)


def schedule_entity_update_threadsafe(entity) -> None:
    """Schedule entity state update on the HA event loop from any thread.

    Dispatcher callbacks can run on a worker thread. Calling entity state write
    helpers from that thread is not thread-safe.
    """
    hass = getattr(entity, "hass", None)
    if hass is None:
        return
    try:
        hass.loop.call_soon_threadsafe(entity.async_schedule_update_ha_state)
    except RuntimeError:
        # Event loop may be closing during shutdown
        return
