from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


AVCUI_SELECTS = [
    {
        "key": "dialnorm",
        "name": "Dialnorm",
        "options": ["not set", "off", "on"],
        "command_prefix": "dialnorm",
    },
]


def build_avcui_select_entities(htp1, entry_id: str):
    return [
        Htp1AvcuiSelect(
            htp1=htp1,
            entry_id=entry_id,
            key=cfg["key"],
            name=cfg["name"],
            options=cfg["options"],
            command_prefix=cfg["command_prefix"],
        )
        for cfg in AVCUI_SELECTS
    ]


class Htp1AvcuiSelect(SelectEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        htp1,
        entry_id: str,
        key: str,
        name: str,
        options: list[str],
        command_prefix: str,
    ):
        self._htp1 = htp1
        self._entry_id = entry_id
        self._command_prefix = command_prefix

        self._attr_unique_id = f"{entry_id}_avcui_sel_{key}"
        self._attr_name = name
        self._attr_options = options

        self._attr_current_option = None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Monoprice",
            model="HTP-1",
            name="HTP-1",
        )

    @property
    def available(self):
        return self._htp1.connected

    async def async_added_to_hass(self) -> None:
        self._attr_current_option = None
        self.async_write_ha_state()


    async def async_select_option(self, option: str) -> None:
        if option == "not set":
            self._attr_current_option = None
            self.async_write_ha_state()
            return

        await self._htp1.send_avcui(f"{self._command_prefix} {option}")
        self._attr_current_option = option
        self.async_write_ha_state()











