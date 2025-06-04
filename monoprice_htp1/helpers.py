"""Helpers for the Monoprice HTP-1 component."""

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

_client_timeout = aiohttp.ClientTimeout(
    total=30,
    connect=10,
    sock_read=5,
    sock_connect=None,
)


def async_get_clientsession(hass: HomeAssistant) -> aiohttp.ClientSession:
    """Create a aiohttp ClientSession with the desired timeout setup."""
    return async_create_clientsession(hass, timeout=_client_timeout)
