from __future__ import annotations

import logging
from typing import Any, Callable

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, ui_lock_signal
from .helpers import schedule_entity_update_threadsafe

_LOGGER = logging.getLogger(__name__)

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
    {
        "key": "secondary_volume",
        "name": "Mix Out Volume",
        "path": "/secondaryVolume",
        "min": lambda h: h.cal_vpl,
        "max": lambda h: h.cal_vph,
        "step": 1,
        "get_fn": lambda h: h.secondary_volume,
        "set_fn": lambda h, v: setattr(h, "secondary_volume", v),
    },
    {
        "key": "secondary_poweron_volume",
        "name": "Mix Out Power On Volume",
        "path": "/secondaryPowerOnVolume",
        "min": lambda h: h.cal_vpl,
        "max": lambda h: h.cal_vph,
        "step": 1,
        "get_fn": lambda h: h.secondary_poweron_volume,
        "set_fn": lambda h, v: setattr(h, "secondary_poweron_volume", v),
    },
    {
        "key": "dialogenh",
        "name": "Dialog Enhance",
        "path": "/dialogEnh",
        "min": 0,
        "max": 6,
        "step": 1,
        "get_fn": lambda h: h.dialogenh,
        "set_fn": lambda h, v: setattr(h, "dialogenh", v),
    },
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
        "key": "display_brightness",
        "name": "Display Brightness",
        "path": "/hw/fpBright",
        "min": 0,
        "max": 7,
        "step": 1,
        "get_fn": lambda h: h.display_brightness,
        "set_fn": lambda h, v: setattr(h, "display_brightness", v),
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
        "get_fn": lambda h: h.cal_current_dirac_slot,
        "set_fn": lambda h, v: setattr(h, "cal_current_dirac_slot", int(v)),
    },
    {
        "key": "channeltrim_right",
        "name": "Trim Right",
        "path": "/channeltrim/channels/rf",
        "min": -12,
        "max": 12,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_right,
        "set_fn": lambda h, v: setattr(h, "channeltrim_right", v),
    },
    {
        "key": "channeltrim_left",
        "name": "Trim Left",
        "path": "/channeltrim/channels/lf",
        "min": -12,
        "max": 12,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_left,
        "set_fn": lambda h, v: setattr(h, "channeltrim_left", v),
    },
    {
        "key": "channeltrim_center",
        "name": "Trim Center",
        "path": "/channeltrim/channels/c",
        "min": -12,
        "max": 12,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_center,
        "set_fn": lambda h, v: setattr(h, "channeltrim_center", v),
    },
    {
        "key": "channeltrim_lfe",
        "name": "Trim LFE",
        "path": "/channeltrim/channels/lfe",
        "min": -12,
        "max": 12,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_lfe,
        "set_fn": lambda h, v: setattr(h, "channeltrim_lfe", v),
    },
    {
        "key": "channeltrim_rightsurround",
        "name": "Trim Right Surround",
        "path": "/channeltrim/channels/rs",
        "min": -12,
        "max": 12,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_rightsurround,
        "set_fn": lambda h, v: setattr(h, "channeltrim_rightsurround", v),
    },
    {
        "key": "channeltrim_leftsurround",
        "name": "Trim Left Surround",
        "path": "/channeltrim/channels/ls",
        "min": -12,
        "max": 12,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_leftsurround,
        "set_fn": lambda h, v: setattr(h, "channeltrim_leftsurround", v),
    },
    {
        "key": "channeltrim_rightback",
        "name": "Trim Right Back",
        "path": "/channeltrim/channels/rb",
        "min": -12,
        "max": 12,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_rightback,
        "set_fn": lambda h, v: setattr(h, "channeltrim_rightback", v),
    },
    {
        "key": "channeltrim_leftback",
        "name": "Trim Left Back",
        "path": "/channeltrim/channels/lb",
        "min": -12,
        "max": 12,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_leftback,
        "set_fn": lambda h, v: setattr(h, "channeltrim_leftback", v),
    },
    {
        "key": "channeltrim_ltf",
        "name": "Trim Left Top Front",
        "path": "/channeltrim/channels/ltf",
        "min": -12,
        "max": 12,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_ltf,
        "set_fn": lambda h, v: setattr(h, "channeltrim_ltf", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_rtf",
        "name": "Trim Right Top Front",
        "path": "/channeltrim/channels/rtf",
        "min": -12,
        "max": 12,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_rtf,
        "set_fn": lambda h, v: setattr(h, "channeltrim_rtf", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_ltm",
        "name": "Trim Left Top Middle",
        "path": "/channeltrim/channels/ltm",
        "min": -12,
        "max": 12,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_ltm,
        "set_fn": lambda h, v: setattr(h, "channeltrim_ltm", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_rtm",
        "name": "Trim Right Top Middle",
        "path": "/channeltrim/channels/rtm",
        "min": -12,
        "max": 12,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_rtm,
        "set_fn": lambda h, v: setattr(h, "channeltrim_rtm", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_ltr",
        "name": "Trim Left Top Rear",
        "path": "/channeltrim/channels/ltr",
        "min": -12,
        "max": 12,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_ltr,
        "set_fn": lambda h, v: setattr(h, "channeltrim_ltr", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_rtr",
        "name": "Trim Right Top Rear",
        "path": "/channeltrim/channels/rtr",
        "min": -12,
        "max": 12,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_rtr,
        "set_fn": lambda h, v: setattr(h, "channeltrim_rtr", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_lw",
        "name": "Trim Left Wide",
        "path": "/channeltrim/channels/lw",
        "min": -12,
        "max": 12,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_lw,
        "set_fn": lambda h, v: setattr(h, "channeltrim_lw", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_rw",
        "name": "Trim Right Wide",
        "path": "/channeltrim/channels/rw",
        "min": -12,
        "max": 12,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_rw,
        "set_fn": lambda h, v: setattr(h, "channeltrim_rw", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_lfh",
        "name": "Trim Left Front Height",
        "path": "/channeltrim/channels/lfh",
        "min": -12,
        "max": 12,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_lfh,
        "set_fn": lambda h, v: setattr(h, "channeltrim_lfh", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_rfh",
        "name": "Trim Right Front Height",
        "path": "/channeltrim/channels/rfh",
        "min": -12,
        "max": 12,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_rfh,
        "set_fn": lambda h, v: setattr(h, "channeltrim_rfh", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_lhb",
        "name": "Trim Left Height Back",
        "path": "/channeltrim/channels/lhb",
        "min": -12,
        "max": 12,
        "step": 0.25,
        "get_fn": lambda h: h.channeltrim_lhb,
        "set_fn": lambda h, v: setattr(h, "channeltrim_lhb", v),
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_rhb",
        "name": "Trim Right Height Back",
        "path": "/channeltrim/channels/rhb",
        "min": -12,
        "max": 12,
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
# HTP-1 number entities
# -------------------------------------------------------------
def build_htp1_numbers(htp1, entry_id: str):
    entities = []
    for cfg in NUMBER_DEFINITIONS:
        mode = NumberMode.BOX if cfg.get("mode") == "box" else None
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
                entity_registry_enabled_default=cfg.get(
                    "entity_registry_enabled_default", True
                ),
                icon=cfg.get("icon"),
                mode=mode,
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

    # Mix-out tracking parameters (local RestoreEntity numbers, no device path).
    from .mix_out_tracker import build_mix_out_tracking_numbers
    entities.extend(build_mix_out_tracking_numbers(htp1, entry.entry_id))

    # Request an immediate first update so entities don't sit at unknown.
    async_add_entities(entities, True)


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
        min,
        max,
        step: float,
        get_fn: Callable[[Any], Any],
        set_fn: Callable[[Any, Any], None],
        entity_registry_enabled_default: bool = True,
        icon: str | None = None,
        mode: NumberMode | None = None,
    ):
        self._htp1 = htp1
        self._path = path
        self._get_fn = get_fn
        self._set_fn = set_fn
        self._key = key
        self._entry_id = entry_id

        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._min = min
        self._max = max
        self._attr_native_step = step

        if mode is not None:
            self._attr_mode = mode
        elif key == "cal_current_dirac_slot":
            # Backward compatibility: if definition doesn't specify mode, keep BOX for Dirac slot.
            self._attr_mode = NumberMode.BOX

        self._attr_entity_registry_enabled_default = entity_registry_enabled_default

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Monoprice",
            model="HTP-1",
            name="HTP-1",
        )

    def _resolve_limit(self, v):
        try:
            return v(self._htp1) if callable(v) else v
        except Exception:
            _LOGGER.debug(
                "Failed to resolve limit for key=%s path=%s",
                self._key,
                self._path,
                exc_info=True,
            )
            return None

    @property
    def native_min_value(self):
        value = self._resolve_limit(self._min)
        if value is not None:
            return value

        # Fallbacks when calibration values are not available yet.
        if self._key in ("volume", "secondary_volume", "secondary_poweron_volume"):
            return -70
        return -12

    @property
    def native_max_value(self):
        value = self._resolve_limit(self._max)
        if value is not None:
            return value

        if self._key in ("volume", "secondary_volume", "secondary_poweron_volume"):
            return -1
        return 12

    @property
    def available(self) -> bool:
        if not self._htp1.connected:
            return False

        # Volume must always be locked when the device is explicitly OFF/standby,
        # regardless of the UI lock toggle state.
        if self._key == "volume":
            pwr = getattr(self._htp1, "power", None)
            if pwr is False or pwr == 0:
                return False
            return True

        # Other numbers: lock only if the UI lock toggle is enabled.
        if getattr(self._htp1, "lock_controls_when_off", True):
            pwr = getattr(self._htp1, "power", None)
            if pwr is False or pwr == 0:
                return False

        return True

    @property
    def native_value(self):
        try:
            # Lock volume display when device is off/sleep.
            if self._key == "volume":
                pwr = getattr(self._htp1, "power", None)
                if pwr is False or pwr == 0:
                    return self._htp1.power_on_vol

            v = self._get_fn(self._htp1)
            if v is None:
                return None

            # UI uses 1..3, device uses 0..2.
            if self._key == "cal_current_dirac_slot":
                return int(v) + 1

            return v
        except Exception:
            _LOGGER.debug(
                "Failed to compute native_value for key=%s path=%s",
                self._key,
                self._path,
                exc_info=True,
            )
            return None

    async def async_set_native_value(self, value):
        async with self._htp1:
            # UI uses 1..3, device expects 0..2.
            if self._key == "cal_current_dirac_slot":
                value = int(value) - 1

            # Lock volume when device is off/sleep.
            if self._key == "volume":
                pwr = getattr(self._htp1, "power", None)
                if pwr is False or pwr == 0:
                    value = self._htp1.power_on_vol

            self._set_fn(self._htp1, value)
            await self._htp1.commit()

    async def async_added_to_hass(self):
        self._unsubs = []

        # Subscribe to path updates from the device.
        unsub = self._htp1.subscribe(self._path, self._handle_update)
        if callable(unsub):
            self._unsubs.append(unsub)

        # Volume UI availability/value depends also on power and power-on volume.
        if self._key == "volume":
            unsub = self._htp1.subscribe("/powerIsOn", self._handle_update)
            if callable(unsub):
                self._unsubs.append(unsub)
            unsub = self._htp1.subscribe("/powerOnVol", self._handle_update)
            if callable(unsub):
                self._unsubs.append(unsub)

        # Availability depends on power/connection and UI lock.
        if self._path != "/powerIsOn":
            unsub = self._htp1.subscribe("/powerIsOn", self._handle_update)
            if callable(unsub):
                self._unsubs.append(unsub)

        unsub = self._htp1.subscribe("#connection", self._handle_update)
        if callable(unsub):
            self._unsubs.append(unsub)

        self._unsub_ui_lock = async_dispatcher_connect(
            self.hass, ui_lock_signal(self._entry_id), self._handle_update
        )

    async def async_will_remove_from_hass(self) -> None:
        for unsub in getattr(self, "_unsubs", []):
            if callable(unsub):
                try:
                    unsub()
                except Exception:
                    pass

        unsub = getattr(self, "_unsub_ui_lock", None)
        if callable(unsub):
            try:
                unsub()
            except Exception:
                pass

    def _handle_update(self, *args):
        schedule_entity_update_threadsafe(self)
