from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


def build_avcui_button_entities(htp1, entry_id: str):
    return [
        Htp1AvcuiButton(
            htp1=htp1,
            entry_id=entry_id,
            key="hpe",
            name="HDMI Reset",
            command="hpe",
            icon="mdi:button-pointer",
        )
    ]


class Htp1AvcuiButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        htp1,
        entry_id: str,
        key: str,
        name: str,
        command: str,
        icon: str | None = None,
    ):
        self._htp1 = htp1
        self._entry_id = entry_id
        self._command = command

        self._attr_unique_id = f"{entry_id}_avcui_btn_{key}"
        self._attr_name = name
        self._attr_icon = icon

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Monoprice",
            model="HTP-1",
            name="HTP-1",
        )

    @property
    def available(self):
        return self._htp1.connected

    async def async_press(self) -> None:
        await self._htp1.send_avcui(self._command)
