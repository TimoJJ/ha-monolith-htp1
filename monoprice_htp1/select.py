from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, ui_lock_signal
from .helpers import schedule_entity_update_threadsafe

_LOGGER = logging.getLogger(__name__)

# Optional AVCUI select support
try:
    from .avcui_select import build_avcui_select_entities  # type: ignore
except Exception as err:
    build_avcui_select_entities = None  # type: ignore
    _LOGGER.debug("AVCUI select disabled (avcui_select.py): %s", err)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    htp1 = hass.data[DOMAIN][entry.entry_id]

    entities = [
        Htp1InputSelect(htp1, entry),
        Htp1UpmixSelect(htp1, entry),
        Htp1LoudnessCurveSelect(htp1, entry),
        Htp1DiracActiveSelect(htp1, entry),
    ]


    # Add AVCUI selects only if module import succeeded
    if build_avcui_select_entities is not None:
        try:
            entities += build_avcui_select_entities(htp1, entry.entry_id)
        except Exception:
            _LOGGER.error("Failed to build AVCUI select entities", exc_info=True)

    # Consistent behavior with other platforms: request an immediate first update
    async_add_entities(entities, True)


class Htp1BaseSelect(SelectEntity):
    """Base class for HTP-1 selects."""

    _attr_has_entity_name = True

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
    def available(self) -> bool:
        if not self._htp1.connected:
            return False

        # Lock selects when device is explicitly OFF/standby and UI lock is enabled.
        if getattr(self._htp1, "lock_controls_when_off", True):
            pwr = getattr(self._htp1, "power", None)
            if pwr is False or pwr == 0:
                return False

        return True


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
        # Enforce UI lock even if called via service.
        if getattr(self._htp1, "lock_controls_when_off", True):
            pwr = getattr(self._htp1, "power", None)
            if pwr is False or pwr == 0:
                return

        async with self._htp1:
            self._htp1.input = option
            await self._htp1.commit()

    async def async_added_to_hass(self):
        # Use a sync callback to avoid coroutine creation if subscribe() is sync.
        self._unsubs = []

        unsub = self._htp1.subscribe("/input", self._handle_update)
        if callable(unsub):
            self._unsubs.append(unsub)

        # Availability depends on power/connection + UI lock; update immediately on change
        unsub = self._htp1.subscribe("/powerIsOn", self._handle_update)
        if callable(unsub):
            self._unsubs.append(unsub)

        unsub = self._htp1.subscribe("#connection", self._handle_update)
        if callable(unsub):
            self._unsubs.append(unsub)

        self._unsub_ui_lock = async_dispatcher_connect(
            self.hass, ui_lock_signal(self._entry.entry_id), self._handle_update
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
            unsub()

    def _handle_update(self, *args):
        schedule_entity_update_threadsafe(self)


class Htp1UpmixSelect(Htp1BaseSelect):
    _attr_name = "Upmix"
    _attr_icon = "mdi:arrow-expand-up"

    _RAW_TO_UI: dict[str, str] = {
        "off": "Direct",
        "native": "Native",
        "dolby": "Dolby Surround",
        "dts": "DTS Neural:X",
        "auro": "Auro-3D",
        "mono": "Mono",
        "stereo": "Stereo",
    }

    def __init__(self, htp1, entry: ConfigEntry) -> None:
        super().__init__(htp1, entry)
        self._attr_unique_id = f"{entry.entry_id}_upmix"
        self._ui_to_raw: dict[str, str] = {}
        self._raw_to_ui: dict[str, str] = {}

    def _format_ui(self, raw: str) -> str:
        if raw in self._RAW_TO_UI:
            return self._RAW_TO_UI[raw]
        return str(raw).replace("_", " ").replace("-", " ").title()

    def _rebuild_maps(self, raws: list[str]) -> None:
        self._raw_to_ui.clear()
        self._ui_to_raw.clear()
        for raw in raws:
            raw_str = str(raw)
            ui = self._format_ui(raw_str)
            self._raw_to_ui[raw_str] = ui
            self._ui_to_raw.setdefault(ui, raw_str)

    @property
    def options(self) -> list[str]:
        try:
            raws = list(self._htp1.upmixes or [])
        except Exception:
            raws = []

        self._rebuild_maps(raws)
        return [self._raw_to_ui[r] for r in raws]

    @property
    def current_option(self) -> str | None:
        try:
            raw = self._htp1.upmix
            if raw is None:
                return None

            raw_str = str(raw)
            if raw_str not in self._raw_to_ui:
                self._rebuild_maps(list(self._htp1.upmixes or []))

            return self._raw_to_ui.get(raw_str, self._format_ui(raw_str))
        except Exception:
            return None

    async def async_select_option(self, option: str) -> None:
        # Enforce UI lock even if called via service.
        if getattr(self._htp1, "lock_controls_when_off", True):
            pwr = getattr(self._htp1, "power", None)
            if pwr is False or pwr == 0:
                return

        raw = self._ui_to_raw.get(option, option)

        async with self._htp1:
            self._htp1.upmix = raw
            await self._htp1.commit()

        # Must be thread-safe (commit callbacks / dispatcher can involve non-loop threads)
        schedule_entity_update_threadsafe(self)

    async def async_added_to_hass(self):
        self._unsubs = []

        unsub = self._htp1.subscribe("/upmix/select", self._handle_update)
        if callable(unsub):
            self._unsubs.append(unsub)

        # Availability depends on power/connection + UI lock; update immediately on change
        unsub = self._htp1.subscribe("/powerIsOn", self._handle_update)
        if callable(unsub):
            self._unsubs.append(unsub)

        unsub = self._htp1.subscribe("#connection", self._handle_update)
        if callable(unsub):
            self._unsubs.append(unsub)

        self._unsub_upmix_ui_lock = async_dispatcher_connect(
            self.hass, ui_lock_signal(self._entry.entry_id), self._handle_update
        )

    async def async_will_remove_from_hass(self) -> None:
        for unsub in getattr(self, "_unsubs", []):
            if callable(unsub):
                try:
                    unsub()
                except Exception:
                    pass

        unsub = getattr(self, "_unsub_upmix_ui_lock", None)
        if callable(unsub):
            unsub()

    def _handle_update(self, *args):
        schedule_entity_update_threadsafe(self)


class Htp1LoudnessCurveSelect(Htp1BaseSelect):
    _attr_name = "Loudness Curve"
    _attr_icon = "mdi:chart-bell-curve"

    # raw -> UI
    _RAW_TO_UI: dict[str, str] = {
        "iso": "ISO 226:2003",
        "vintage": "Vintage",
    }

    # UI -> raw
    _UI_TO_RAW: dict[str, str] = {v: k for k, v in _RAW_TO_UI.items()}

    def __init__(self, htp1, entry: ConfigEntry) -> None:
        super().__init__(htp1, entry)
        self._attr_unique_id = f"{entry.entry_id}_loudness_curve"

    @property
    def options(self) -> list[str]:
        # UI-nimet Home Assistantiin
        return list(self._RAW_TO_UI.values())

    @property
    def current_option(self) -> str | None:
        try:
            raw = self._htp1.loudness_curve
            if raw is None:
                return None
            return self._RAW_TO_UI.get(str(raw))
        except Exception:
            return None

    async def async_select_option(self, option: str) -> None:
        if getattr(self._htp1, "lock_controls_when_off", True):
            pwr = getattr(self._htp1, "power", None)
            if pwr is False or pwr == 0:
                return

        raw = self._UI_TO_RAW.get(option)
        if raw is None:
            return

        async with self._htp1:
            self._htp1.loudness_curve = raw
            await self._htp1.commit()

        schedule_entity_update_threadsafe(self)

    async def async_added_to_hass(self):
        self._unsubs = []

        unsub = self._htp1.subscribe("/loudnessCurve", self._handle_update)
        if callable(unsub):
            self._unsubs.append(unsub)

        unsub = self._htp1.subscribe("/powerIsOn", self._handle_update)
        if callable(unsub):
            self._unsubs.append(unsub)

        unsub = self._htp1.subscribe("#connection", self._handle_update)
        if callable(unsub):
            self._unsubs.append(unsub)

        self._unsub_ui_lock = async_dispatcher_connect(
            self.hass, ui_lock_signal(self._entry.entry_id), self._handle_update
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
            unsub()

    def _handle_update(self, *args):
        schedule_entity_update_threadsafe(self)


class Htp1DiracActiveSelect(Htp1BaseSelect):
    _attr_name = "Dirac Active"
    _attr_icon = "mdi:alpha-d-box"

    # raw -> UI
    _RAW_TO_UI: dict[str, str] = {
        "on": "On",
        "bypass": "Bypass",
        "off": "Off",
    }

    # UI -> raw
    _UI_TO_RAW: dict[str, str] = {v: k for k, v in _RAW_TO_UI.items()}

    def __init__(self, htp1, entry: ConfigEntry) -> None:
        super().__init__(htp1, entry)
        self._attr_unique_id = f"{entry.entry_id}_dirac_active"

    @property
    def options(self) -> list[str]:
        return list(self._RAW_TO_UI.values())

    @property
    def current_option(self) -> str | None:
        try:
            raw = self._htp1.dirac_active
            if raw is None:
                return None
            return self._RAW_TO_UI.get(str(raw))
        except Exception:
            return None

    async def async_select_option(self, option: str) -> None:
        if getattr(self._htp1, "lock_controls_when_off", True):
            pwr = getattr(self._htp1, "power", None)
            if pwr is False or pwr == 0:
                return

        raw = self._UI_TO_RAW.get(option)
        if raw is None:
            return

        async with self._htp1:
            self._htp1.dirac_active = raw
            await self._htp1.commit()

        schedule_entity_update_threadsafe(self)

    async def async_added_to_hass(self):
        self._unsubs = []

        unsub = self._htp1.subscribe("/cal/diracactive", self._handle_update)
        if callable(unsub):
            self._unsubs.append(unsub)

        unsub = self._htp1.subscribe("/powerIsOn", self._handle_update)
        if callable(unsub):
            self._unsubs.append(unsub)

        unsub = self._htp1.subscribe("#connection", self._handle_update)
        if callable(unsub):
            self._unsubs.append(unsub)

        self._unsub_ui_lock = async_dispatcher_connect(
            self.hass, ui_lock_signal(self._entry.entry_id), self._handle_update
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
            unsub()

    def _handle_update(self, *args):
        schedule_entity_update_threadsafe(self)
