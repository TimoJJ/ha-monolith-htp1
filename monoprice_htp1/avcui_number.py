from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.storage import Store

from .const import DOMAIN


STORAGE_VERSION = 1
STORAGE_KEY_TEMPLATE = f"{DOMAIN}_avcui_number_{{entry_id}}"


AVCUI_NUMBERS = [
    {
        "key": "secondary_volume",
        "name": "Secondary Volume",
        "command": "sec vol",
        "min": -70,
        "max": -1,
        "step": 1,
        "state_var": "sec_vol",
    },
]


def build_avcui_number_entities(hass, htp1, entry_id: str):

    return [
        Htp1AvcuiNumber(
            hass=hass,
            htp1=htp1,
            entry_id=entry_id,
            key=cfg["key"],
            name=cfg["name"],
            command_prefix=cfg["command"],
            minimum=cfg["min"],
            maximum=cfg["max"],
            step=cfg["step"],
        )
        for cfg in AVCUI_NUMBERS
    ]


class Htp1AvcuiNumber(NumberEntity):

    _attr_has_entity_name = True

    def __init__(
        self,
        hass,
        htp1,
        entry_id: str,
        key: str,
        name: str,
        command_prefix: str,
        minimum: int,
        maximum: int,
        step: int,
    ):
        self._hass = hass
        self._htp1 = htp1
        self._entry_id = entry_id
        self._command_prefix = command_prefix
        self._key = key


        self._store = Store(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY_TEMPLATE.format(entry_id=entry_id),
        )

        self._current_value = None

        self._attr_unique_id = f"{entry_id}_avcui_{key}"
        self._attr_name = name
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Monoprice",
            model="HTP-1",
            name="HTP-1",
        )

    @property
    def available(self):
        return self._htp1.connected

    @property
    def native_value(self):

        if self._current_value is None:
            return self._attr_native_min_value
        return self._current_value

    async def async_added_to_hass(self):

        data = await self._store.async_load()
        if data and self._key in data:
            self._current_value = data[self._key]

        self.async_write_ha_state()

    async def async_set_native_value(self, value):
        value = int(value)
        self._current_value = value


        cmd = f"{self._command_prefix} {value}"
        await self._htp1.send_avcui(cmd)


        await self._store.async_save({self._key: self._current_value})

        self.async_write_ha_state()
