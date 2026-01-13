from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


AVCUI_SWITCHES = [
    {
        "key": "secondary_mute",
        "name": "Secondary Mute",
        "command_on": "sec mute on",
        "command_off": "sec mute off",
    },
]


def build_avcui_entities(htp1, entry_id: str):
    return [
        Htp1AvcuiSwitch(
            htp1=htp1,
            entry_id=entry_id,
            key=cfg["key"],
            name=cfg["name"],
            command_on=cfg["command_on"],
            command_off=cfg["command_off"],
        )
        for cfg in AVCUI_SWITCHES
    ]


class Htp1AvcuiSwitch(SwitchEntity):
    """One-way AVCUI switch (not tied to websocket state)."""

    _attr_has_entity_name = True

    def __init__(self, htp1, entry_id, key, name, command_on, command_off):
        self._htp1 = htp1
        self._command_on = command_on
        self._command_off = command_off

        self._attr_unique_id = f"{entry_id}_avcui_{key}"
        self._attr_name = name
        self._is_on = False

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Monoprice",
            model="HTP-1",
            name="HTP-1",
        )

    @property
    def is_on(self):
        return self._is_on

    async def async_turn_on(self):
        await self._htp1.send_avcui(self._command_on)
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self):
        await self._htp1.send_avcui(self._command_off)
        self._is_on = False
        self.async_write_ha_state()
