from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .avcui_button import build_avcui_button_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up HTP-1 button entities."""
    htp1 = hass.data[DOMAIN][entry.entry_id]

    entities = []
    entities.extend(build_avcui_button_entities(htp1, entry.entry_id))

    # Buttons are stateless; no need to wait for updates,
    # but keep behavior consistent with other platforms.
    async_add_entities(entities, True)
