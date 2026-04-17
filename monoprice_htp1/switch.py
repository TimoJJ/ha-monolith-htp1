from __future__ import annotations

import logging
from typing import Any, Callable

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send

from .const import DOMAIN, ui_lock_signal
from .helpers import schedule_entity_update_threadsafe

_LOGGER = logging.getLogger(__name__)


# -------------------------------------------------------------
#  HTP-1 switches
# -------------------------------------------------------------
SWITCH_DEFINITIONS = [
    {
        "key": "power",
        "name": "Power",
        "path": "/powerIsOn",
        "icon": "mdi:power",
        "get_fn": lambda h: h.power,
        "set_fn": lambda h, v: setattr(h, "power", v),
    },
    {
        "key": "tone_control",
        "name": "Tone Control",
        "path": "/eq/tc",
        "icon": "mdi:music-note",
        "get_fn": lambda h: h.tone_control,
        "set_fn": lambda h, v: setattr(h, "tone_control", v),
    },
    {
        "key": "muted",
        "name": "Mute",
        "path": "/muted",
        "icon": "mdi:volume-off",
        "get_fn": lambda h: h.muted,
        "set_fn": lambda h, v: setattr(h, "muted", v),
    },
    {
        "key": "secondary_muted",
        "name": "Mix Out Mute",
        "path": "/secondaryMuted",
        "icon": "mdi:volume-off",
        "get_fn": lambda h: h.secondary_muted,
        "set_fn": lambda h, v: setattr(h, "secondary_muted", v),
    },
    {
        "key": "loudness_status",
        "name": "Loudness",
        "path": "/loudness",
        "icon": "mdi:ear-hearing",
        "get_fn": lambda h: h.loudness_status,
        "set_fn": lambda h, v: setattr(h, "loudness_status", v),
    },

    {
        "key": "widesynth",
        "name": "Widesynth",
        "path": "/upmix/dts/ws",
        "icon": "mdi:arrow-split-vertical",
        "get_fn": lambda h: h.widesynth,
        "set_fn": lambda h, v: setattr(h, "widesynth", v),
    },
    {
        "key": "aurohs",
        "name": "Auro High Sides",
        "path": "/upmix/auro/highSides",
        "icon": "mdi:align-vertical-top",
        "get_fn": lambda h: h.aurohs,
        "set_fn": lambda h, v: setattr(h, "aurohs", v),
    },
]


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
                icon=cfg.get("icon"),
                entity_registry_enabled_default=cfg.get(
                    "entity_registry_enabled_default", True
                ),
            )
        )
    return entities


async def async_setup_entry(hass, entry, async_add_entities):
    htp1 = hass.data[DOMAIN][entry.entry_id]

    entities = []
    entities.extend(build_htp1_switches(htp1, entry.entry_id))

    # Local (hidden) toggle: disable controls when device is off/standby.
    entities.append(Htp1UiLockSwitch(htp1, entry.entry_id))

    # Keep your trigger switches behavior intact.
    from .trigger_switch import build_trigger_switches
    entities.extend(build_trigger_switches(htp1, entry.entry_id))

    # Mix-out volume tracking toggles (switch platform only).
    from .mix_out_tracker import build_mix_out_tracking_switches
    entities.extend(build_mix_out_tracking_switches(htp1, entry.entry_id))

    # Request an immediate first update so entities don't sit at unknown.
    async_add_entities(entities, True)


class Htp1UiLockSwitch(SwitchEntity, RestoreEntity):
    """Local toggle to disable control entities when device is off/standby.

    This switch does NOT map to a device path. It only toggles htp1.lock_controls_when_off.
    """

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = True
    _attr_icon = "mdi:lock"

    def __init__(self, htp1, entry_id: str) -> None:
        self._htp1 = htp1
        self._entry_id = entry_id
        self._attr_unique_id = f"{entry_id}_ui_lock_controls_when_off"
        self._attr_name = "Disable controls in standby"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Monoprice",
            model="HTP-1",
            name="HTP-1",
        )

        self._unsubs: list[Callable[[], None]] = []

    @property
    def available(self) -> bool:
        # The toggle should be available whenever the integration is connected.
        return bool(getattr(self._htp1, "connected", False))

    @property
    def is_on(self) -> bool:
        return bool(getattr(self._htp1, "lock_controls_when_off", True))

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        # Keep availability/state refreshed when connection changes
        unsub = self._htp1.subscribe("#connection", self._handle_update)
        if callable(unsub):
            self._unsubs.append(unsub)

        last = await self.async_get_last_state()
        if last is None:
            # Default: enabled (locked) to match current behavior.
            self._htp1.lock_controls_when_off = True
        else:
            self._htp1.lock_controls_when_off = (last.state == "on")

        # Notify other entities immediately (avoid "stuck" availability until toggled)
        async_dispatcher_send(self.hass, ui_lock_signal(self._entry_id))
        schedule_entity_update_threadsafe(self)

    async def async_will_remove_from_hass(self) -> None:
        for unsub in getattr(self, "_unsubs", []):
            if callable(unsub):
                try:
                    unsub()
                except Exception:
                    pass
        self._unsubs = []

    async def async_turn_on(self, **kwargs) -> None:
        self._htp1.lock_controls_when_off = True
        async_dispatcher_send(self.hass, ui_lock_signal(self._entry_id))
        schedule_entity_update_threadsafe(self)

    async def async_turn_off(self, **kwargs) -> None:
        self._htp1.lock_controls_when_off = False
        async_dispatcher_send(self.hass, ui_lock_signal(self._entry_id))
        schedule_entity_update_threadsafe(self)

    def _handle_update(self, *args):
        schedule_entity_update_threadsafe(self)


class Htp1Switch(SwitchEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        htp1,
        entry_id: str,
        key: str,
        name: str,
        path: str,
        get_fn: Callable[[Any], Any],
        set_fn: Callable[[Any, bool], None],
        icon: str | None = None,
        entity_registry_enabled_default: bool = True,
    ):
        self._htp1 = htp1
        self._entry_id = entry_id
        self._key = key
        self._path = path
        self._get_fn = get_fn
        self._set_fn = set_fn

        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_entity_registry_enabled_default = entity_registry_enabled_default

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Monoprice",
            model="HTP-1",
            name="HTP-1",
        )

        self._unsubs: list[Callable[[], None]] = []

    @property
    def available(self) -> bool:
        if not self._htp1.connected:
            return False

        # Power must always be available.
        if self._key == "power":
            return True

        # Lock switches when device is explicitly OFF/standby and UI lock is enabled.
        if getattr(self._htp1, "lock_controls_when_off", True):
            pwr = getattr(self._htp1, "power", None)
            if pwr is False or pwr == 0:
                return False

        return True

    @property
    def is_on(self) -> bool | None:
        try:
            v = self._get_fn(self._htp1)
            if v is None:
                return None
            return bool(v)
        except Exception:
            _LOGGER.debug(
                "Failed to read switch state for %s", self._path, exc_info=True
            )
            return None

    async def async_turn_on(self, **kwargs):
        # Enforce UI lock even if called via service.
        if self._key != "power" and getattr(self._htp1, "lock_controls_when_off", True):
            pwr = getattr(self._htp1, "power", None)
            if pwr is False or pwr == 0:
                return

        async with self._htp1:
            self._set_fn(self._htp1, True)
            await self._htp1.commit()

        schedule_entity_update_threadsafe(self)

    async def async_turn_off(self, **kwargs):
        # Enforce UI lock even if called via service.
        if self._key != "power" and getattr(self._htp1, "lock_controls_when_off", True):
            pwr = getattr(self._htp1, "power", None)
            if pwr is False or pwr == 0:
                return

        async with self._htp1:
            self._set_fn(self._htp1, False)
            await self._htp1.commit()

        schedule_entity_update_threadsafe(self)

    async def async_added_to_hass(self):
        # Subscribe to own path changes
        unsub = self._htp1.subscribe(self._path, self._handle_update)
        if callable(unsub):
            self._unsubs.append(unsub)

        # Also subscribe to power/connection so availability updates immediately
        if self._path != "/powerIsOn":
            unsub = self._htp1.subscribe("/powerIsOn", self._handle_update)
            if callable(unsub):
                self._unsubs.append(unsub)

        unsub = self._htp1.subscribe("#connection", self._handle_update)
        if callable(unsub):
            self._unsubs.append(unsub)

        # And UI lock changes
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
        self._unsubs = []

        unsub = getattr(self, "_unsub_ui_lock", None)
        if callable(unsub):
            try:
                unsub()
            except Exception:
                pass

    def _handle_update(self, *args):
        schedule_entity_update_threadsafe(self)
