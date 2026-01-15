from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .avcui_number import build_avcui_number_entities
from .const import DOMAIN
from homeassistant.components.number import NumberMode


# -------------------------------------------------------------
#  HTP-1 Numbers
# -------------------------------------------------------------
NUMBER_DEFINITIONS = [
    {
        "key": "volume",
        "name": "Volume",
        "path": "/volume",
        "min": lambda h: h.cal_vpl,
        "max": lambda h: h.cal_vph,
        "step": 1,
        "get_fn": lambda h: h.volume,
        "set_fn": lambda h, v: setattr(h, "volume", v),
    },
#    {
#        "key": "secondvolume",
#        "name": "Secondary Volume mso",
#        "path": "/secondVolume",
#        "min": lambda h: h.cal_vpl,
#        "max": lambda h: h.cal_vph,
#        "step": 1,
#        "get_fn": lambda h: h.secondvolume,
#        "set_fn": lambda h, v: setattr(h, "secondvolume", v),
#        "entity_registry_enabled_default": False,
#    },
    {
        "key": "bass_level",
        "name": "Bass Level",
        "path": "/eq/bass/level",
        "min": -12,
        "max": 12,
        "step": 1,
        "get_fn": lambda h: h.bass_level,
        "set_fn": lambda h, v: setattr(h, "bass_level", v),
    },
    {
        "key": "bass_frequency",
        "name": "Bass Corner Frequency",
        "path": "/eq/bass/freq",
        "min": 20,
        "max": 200,
        "step": 1,
        "get_fn": lambda h: h.bass_frequency,
        "set_fn": lambda h, v: setattr(h, "bass_frequency", v),
    },
    {
        "key": "treble_level",
        "name": "Treble Level",
        "path": "/eq/treble/level",
        "min": -12,
        "max": 12,
        "step": 1,
        "get_fn": lambda h: h.treble_level,
        "set_fn": lambda h, v: setattr(h, "treble_level", v),
    },
    {
        "key": "treble_frequency",
        "name": "Treble Corner Frequency",
        "path": "/eq/treble/freq",
        "min": 2500,
        "max": 8000,
        "step": 100,
        "get_fn": lambda h: h.treble_frequency,
        "set_fn": lambda h, v: setattr(h, "treble_frequency", v),
    },
    {
        "key": "lipsync_delay",
        "name": "Lipsync Delay",
        "path": "/cal/lipsync",
        "min": 0,
        "max": 340,
        "step": 1,
        "get_fn": lambda h: h.lipsync_delay,
        "set_fn": lambda h, v: setattr(h, "lipsync_delay", v),
    },
    {
        "key": "cal_current_dirac_slot",
        "name": "Calibration Slot",
        "path": "/cal/currentdiracslot",
        "icon": "mdi:playlist-check",
        "mode": "box",
        "min": 1,
        "max": 3,
        "step": 1,
        "get_fn": lambda htp1: htp1.cal_current_dirac_slot,
        "set_fn": lambda h, v: setattr(h, "cal_current_dirac_slot", int(v)),
    },

    {
        "key": "channeltrim_right",
        "name": "Trim Right",
        "path": "/channeltrim/channels/rf",
        "min": -6,
        "max": 6,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_right,
        "set_fn": lambda h, v: setattr(h, "channeltrim_right", v),
    },
    {
        "key": "channeltrim_left",
        "name": "Trim Left",
        "path": "/channeltrim/channels/lf",
        "min": -6,
        "max": 6,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_left,
        "set_fn": lambda h, v: setattr(h, "channeltrim_left", v),
    },
    {
        "key": "channeltrim_center",
        "name": "Trim Center",
        "path": "/channeltrim/channels/c",
        "min": -6,
        "max": 6,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_center,
        "set_fn": lambda h, v: setattr(h, "channeltrim_center", v),
    },
    {
        "key": "channeltrim_lfe",
        "name": "Trim LFE",
        "path": "/channeltrim/channels/lfe",
        "min": -6,
        "max": 6,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_lfe,
        "set_fn": lambda h, v: setattr(h, "channeltrim_lfe", v),
    },
    {
        "key": "channeltrim_rightsurround",
        "name": "Trim Right Surround",
        "path": "/channeltrim/channels/rs",
        "min": -6,
        "max": 6,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_rightsurround,
        "set_fn": lambda h, v: setattr(h, "channeltrim_rightsurround", v),
    },
    {
        "key": "channeltrim_leftsurround",
        "name": "Trim Left Surround",
        "path": "/channeltrim/channels/ls",
        "min": -6,
        "max": 6,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_leftsurround,
        "set_fn": lambda h, v: setattr(h, "channeltrim_leftsurround", v),
    },
    {
        "key": "channeltrim_rightback",
        "name": "Trim Right Back",
        "path": "/channeltrim/channels/rb",
        "min": -6,
        "max": 6,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_rightback,
        "set_fn": lambda h, v: setattr(h, "channeltrim_rightback", v),
    },
    {
        "key": "channeltrim_leftback",
        "name": "Trim Left Back",
        "path": "/channeltrim/channels/lb",
        "min": -6,
        "max": 6,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_leftback,
        "set_fn": lambda h, v: setattr(h, "channeltrim_leftback", v),
    },

    {
        "key": "channeltrim_ltf",
        "name": "Trim Left Top Front",
        "path": "/channeltrim/channels/ltf",
        "min": -6,
        "max": 6,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_ltf,
        "set_fn": lambda h, v: setattr(h, "channeltrim_ltf", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_rtf",
        "name": "Trim Right Top Front",
        "path": "/channeltrim/channels/rtf",
        "min": -6,
        "max": 6,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_rtf,
        "set_fn": lambda h, v: setattr(h, "channeltrim_rtf", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_ltm",
        "name": "Trim Left Top Middle",
        "path": "/channeltrim/channels/ltm",
        "min": -6,
        "max": 6,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_ltm,
        "set_fn": lambda h, v: setattr(h, "channeltrim_ltm", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_rtm",
        "name": "Trim Right Top Middle",
        "path": "/channeltrim/channels/rtm",
        "min": -6,
        "max": 6,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_rtm,
        "set_fn": lambda h, v: setattr(h, "channeltrim_rtm", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_ltr",
        "name": "Trim Left Top Rear",
        "path": "/channeltrim/channels/ltr",
        "min": -6,
        "max": 6,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_ltr,
        "set_fn": lambda h, v: setattr(h, "channeltrim_ltr", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_rtr",
        "name": "Trim Right Top Rear",
        "path": "/channeltrim/channels/rtr",
        "min": -6,
        "max": 6,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_rtr,
        "set_fn": lambda h, v: setattr(h, "channeltrim_rtr", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_lw",
        "name": "Trim Left Wide",
        "path": "/channeltrim/channels/lw",
        "min": -6,
        "max": 6,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_lw,
        "set_fn": lambda h, v: setattr(h, "channeltrim_lw", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_rw",
        "name": "Trim Right Wide",
        "path": "/channeltrim/channels/rw",
        "min": -6,
        "max": 6,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_rw,
        "set_fn": lambda h, v: setattr(h, "channeltrim_rw", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_lfh",
        "name": "Trim Left Front Height",
        "path": "/channeltrim/channels/lfh",
        "min": -6,
        "max": 6,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_lfh,
        "set_fn": lambda h, v: setattr(h, "channeltrim_lfh", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_rfh",
        "name": "Trim Right Front Height",
        "path": "/channeltrim/channels/rfh",
        "min": -6,
        "max": 6,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_rfh,
        "set_fn": lambda h, v: setattr(h, "channeltrim_rfh", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_lhb",
        "name": "Trim Left Height Back",
        "path": "/channeltrim/channels/lhb",
        "min": -6,
        "max": 6,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_lhb,
        "set_fn": lambda h, v: setattr(h, "channeltrim_lhb", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_rhb",
        "name": "Trim Right Height Back",
        "path": "/channeltrim/channels/rhb",
        "min": -6,
        "max": 6,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_rhb,
        "set_fn": lambda h, v: setattr(h, "channeltrim_rhb", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "loudness_cal",
        "name": "Loudness Calibration",
        "path": "/loudnessCal",
        "min": 60,
        "max": 90,
        "step": 1,
        "get_fn": lambda h: h.loudness_cal,
        "set_fn": lambda h, v: setattr(h, "loudness_cal", v),
    },

]


# -------------------------------------------------------------
# HTP-1 number-entities
# -------------------------------------------------------------
def build_htp1_numbers(htp1, entry_id: str):
    entities = []
    for cfg in NUMBER_DEFINITIONS:
        entities.append(
            Htp1Number(
                htp1=htp1,
                entry_id=entry_id,
                key=cfg["key"],
                name=cfg["name"],
                path=cfg["path"],
                min=cfg["min"],
                max=cfg["max"],
                step=cfg["step"],
                get_fn=cfg["get_fn"],
                set_fn=cfg["set_fn"],
                entity_registry_enabled_default=cfg.get("entity_registry_enabled_default", True),
            )
        )
    return entities


# -------------------------------------------------------------
# Platform setup
# -------------------------------------------------------------
async def async_setup_entry(hass, entry, async_add_entities):
    htp1 = hass.data[DOMAIN][entry.entry_id]

    entities = []
    entities.extend(build_htp1_numbers(htp1, entry.entry_id))
    entities.extend(build_avcui_number_entities(hass, htp1, entry.entry_id))


    async_add_entities(entities)


# -------------------------------------------------------------
# NumberEntity
# -------------------------------------------------------------
class Htp1Number(NumberEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        htp1,
        entry_id: str,
        key: str,
        name: str,
        path: str,
        min: float,
        max: float,
        step: float,
        get_fn,
        set_fn,
        entity_registry_enabled_default: bool = True,
    ):
        self._htp1 = htp1
        self._path = path
        self._get_fn = get_fn
        self._set_fn = set_fn
        self._key = key

        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_name = name
        self._min = min
        self._max = max        
        self._attr_native_step = step
        if key == "cal_current_dirac_slot":
            self._attr_mode = NumberMode.BOX
        self._attr_entity_registry_enabled_default = entity_registry_enabled_default
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Monoprice",
            model="HTP-1",
            name="HTP-1",
        )

    @property
    def available(self):
        return self._htp1.connected


    def _resolve_limit(self, v):
        try:
            return v(self._htp1) if callable(v) else v
        except Exception:
            return None

    @property
    def native_min_value(self):
        value = self._resolve_limit(self._min)
        if value is None:
            # fallback jos cal-data ei vielä ole saatavilla
            return -70 if self._key in ("volume", "secondvolume") else self._min
        return value

    @property
    def native_max_value(self):
        value = self._resolve_limit(self._max)
        if value is None:
            # fallback jos cal-data ei vielä ole saatavilla
            return -1 if self._key in ("volume", "secondvolume") else self._max
        return value



















    @property
    def native_value(self):
        try:
            v = self._get_fn(self._htp1)
            if v is None:
                return None

            # Display Dirac slot as 1..3 in UI, while device uses 0..2
            if self._key == "cal_current_dirac_slot":
                return int(v) + 1

            return v
        except Exception:
            return None

    async def async_set_native_value(self, value):
        async with self._htp1:
            # UI uses 1..3, device expects 0..2
            if self._key == "cal_current_dirac_slot":
                value = int(value) - 1

            self._set_fn(self._htp1, value)
            await self._htp1.commit()

    async def async_added_to_hass(self):
        self._htp1.subscribe(self._path, self._handle_update)

    async def _handle_update(self, value):
        self.async_write_ha_state()
