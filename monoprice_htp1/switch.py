from __future__ import annotations

import asyncio
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .avcui_switch import build_avcui_entities
from .const import DOMAIN
from .entity import Htp1Entity


# -------------------------------------------------------------
#  HTP-1 switches
# -------------------------------------------------------------
SWITCH_DEFINITIONS = [
    {
        "key": "power",
        "name": "Power",
        "path": "/powerIsOn",
        "get_fn": lambda h: h.power,
        "set_fn": lambda h, v: setattr(h, "power", v),
    },
    {
        "key": "tone_control",
        "name": "Tone Control",
        "path": "/eq/tc",
        "get_fn": lambda h: h.tone_control,
        "set_fn": lambda h, v: setattr(h, "tone_control", v),
    },
    {
        "key": "muted",
        "name": "Mute",
        "path": "/muted",
        "get_fn": lambda h: h.muted,
        "set_fn": lambda h, v: setattr(h, "muted", v),
    },
    {
        "key": "loudness_status",
        "name": "Loudness",
        "path": "/loudness",
        "get_fn": lambda h: h.loudness_status,
        "set_fn": lambda h, v: setattr(h, "loudness_status", v),
    },
]


# -------------------------------------------------------------
#  Define HTP-1 switches
# -------------------------------------------------------------
def build_htp1_switches(htp1, entry_id: str):
    entities = []
    for cfg in SWITCH_DEFINITIONS:
        entities.append(
            Htp1Switch(
                htp1=htp1,
                entry_id=entry_id,
                key=cfg["key"],
                name=cfg["name"],
                path=cfg["path"],
                get_fn=cfg["get_fn"],
                set_fn=cfg["set_fn"],
            )
        )
    return entities


# -------------------------------------------------------------
#  HA preps switch-platform
# -------------------------------------------------------------
async def async_setup_entry(hass, entry, async_add_entities):
    htp1 = hass.data[DOMAIN][entry.entry_id]

    entities = []
    entities.extend(build_htp1_switches(htp1, entry.entry_id))
    entities.extend(build_avcui_entities(htp1, entry.entry_id))

    from .trigger_switch import build_trigger_switches
    entities.extend(build_trigger_switches(htp1, entry.entry_id))

    async_add_entities(entities)


# -------------------------------------------------------------
#  Actual switch
# -------------------------------------------------------------
class Htp1Switch(SwitchEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        htp1,
        entry_id: str,
        key: str,
        name: str,
        path: str,
        get_fn,
        set_fn,
    ):
        self._htp1 = htp1
        self._path = path
        self._get_fn = get_fn
        self._set_fn = set_fn

        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_name = name

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
    def is_on(self) -> bool | None:
        try:
            return bool(self._get_fn(self._htp1))
        except Exception:
            return None

    async def async_turn_on(self, **kwargs):
        async with self._htp1:
            self._set_fn(self._htp1, True)
            await self._htp1.commit()

    async def async_turn_off(self, **kwargs):
        async with self._htp1:
            self._set_fn(self._htp1, False)
            await self._htp1.commit()

    async def async_added_to_hass(self):
        self._htp1.subscribe(self._path, self._handle_update)

    async def _handle_update(self, value):
        self.async_write_ha_state()
