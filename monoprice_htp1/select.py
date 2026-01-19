from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from .avcui_select import build_avcui_select_entities

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:

    htp1 = hass.data[DOMAIN][entry.entry_id]

    entities = [
        Htp1InputSelect(htp1, entry),
        Htp1UpmixSelect(htp1, entry),
    ]

    entities += build_avcui_select_entities(htp1, entry.entry_id)

    async_add_entities(entities, update_before_add=False)



class Htp1BaseSelect(SelectEntity):
    """Base class for HTP-1 selects."""

    def __init__(self, htp1, entry: ConfigEntry) -> None:
        self._htp1 = htp1
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Monoprice HTP-1",
            manufacturer="Monoprice",
            model="HTP-1",
        )

    @property
    def available(self):
        return self._htp1.connected


# -------------------------------------------------------------
# Input select
# -------------------------------------------------------------

class Htp1InputSelect(Htp1BaseSelect):
    _attr_name = "Input"
    _attr_icon = "mdi:hdmi-port"

    def __init__(self, htp1, entry: ConfigEntry) -> None:
        super().__init__(htp1, entry)
        self._attr_unique_id = f"{entry.entry_id}_input"

    @property
    def options(self) -> list[str]:
        try:
            return self._htp1.inputs or []
        except Exception:
            return []

    @property
    def current_option(self) -> str | None:
        try:
            return self._htp1.input
        except Exception:
            return None

    async def async_select_option(self, option: str) -> None:
        async with self._htp1:
            self._htp1.input = option
            await self._htp1.commit()

    async def async_added_to_hass(self):
        self._htp1.subscribe("/input", self._handle_update)

    async def _handle_update(self, value):
        self.async_write_ha_state()


# -------------------------------------------------------------
# Upmix select
# -------------------------------------------------------------

class Htp1UpmixSelect(Htp1BaseSelect):
    _attr_name = "Upmix"
    _attr_icon = "mdi:arrow-expand-up"

    def __init__(self, htp1, entry: ConfigEntry) -> None:
        super().__init__(htp1, entry)
        self._attr_unique_id = f"{entry.entry_id}_upmix"

    @property
    def options(self) -> list[str]:
        try:
            return self._htp1.upmixes or []
        except Exception:
            return []

    @property
    def current_option(self) -> str | None:
        try:
            return self._htp1.upmix
        except Exception:
            return None

    async def async_select_option(self, option: str) -> None:
        async with self._htp1:
            self._htp1.upmix = option
            await self._htp1.commit()

    async def async_added_to_hass(self):
        self._htp1.subscribe("/upmix/select", self._handle_update)

    async def _handle_update(self, value):
        self.async_write_ha_state()
