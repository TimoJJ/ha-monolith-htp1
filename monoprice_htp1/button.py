from __future__ import annotations

from .const import DOMAIN
from .avcui_button import build_avcui_button_entities


async def async_setup_entry(hass, entry, async_add_entities):
    htp1 = hass.data[DOMAIN][entry.entry_id]
    entities = build_avcui_button_entities(htp1, entry.entry_id)
    async_add_entities(entities, update_before_add=False)
