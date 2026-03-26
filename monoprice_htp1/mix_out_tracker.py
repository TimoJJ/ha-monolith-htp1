"""Mix Out Volume Tracker for the Monoprice HTP-1 integration.

Provides:
  - MixOutTracker: internal helper that subscribes to /volume and writes
    secondaryVolume to the device whenever tracking is enabled.
  - Htp1MixOutTrackingSwitch: HA switch entity (RestoreEntity) that
    enables/disables tracking and owns the MixOutTracker instance.
  - Five RestoreNumber entities for the tracking parameters:
      * mix_out_tracking_offset  (dB, static offset added to shaped value)
      * mix_out_tracking_thresh  (dB, threshold below which curve kicks in)
      * mix_out_tracking_boost   (dB, maximum boost applied at vol_min)
      * mix_out_tracking_exp     (exponent that controls curve shape)
      * mix_out_tracking_vol_min (dB, floor volume used to normalise t)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, ui_lock_signal
from .helpers import schedule_entity_update_threadsafe

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Curve computation
# ---------------------------------------------------------------------------

def compute_mix_out_volume(
    main: float,
    offset: float,
    thresh: float,
    boost: float,
    exp: float,
    vol_min: float,
    curve_enabled: bool = False,
) -> int:
    """Apply optional non-linear tracking curve and offset, return clamped integer dB.

    When curve_enabled is False the output is simply main + offset (linear tracking).

    When curve_enabled is True:
      Above thresh the output follows main 1:1.
      Below thresh a boost growing towards vol_min is applied,
      shaped by the exponent exp:
        t        = (main - thresh) / (vol_min - thresh)   # 0..1
        t_curved = t ** exp
        shaped   = main + boost * t_curved

    The shaped value is rounded to the nearest integer (1 dB steps) before
    the offset is added, so the final output always moves in 1 dB increments.
    The result is clamped to <= 0 dB before returning.
    """
    if curve_enabled:
        if main >= thresh:
            shaped = main
        else:
            # Guard against division by zero if thresh == vol_min.
            denom = vol_min - thresh
            if denom == 0:
                shaped = main
            else:
                t = (main - thresh) / denom
                t = max(0.0, min(1.0, t))       # clamp t to [0, 1] for safety
                t_curved = t ** exp
                shaped = main + boost * t_curved
        # Round to 1 dB steps so curve output never falls between integer values.
        shaped = round(shaped)
    else:
        shaped = main  # linear: input is already integer dB from device

    value = shaped + offset
    return int(min(value, 0))


# ---------------------------------------------------------------------------
# Internal tracker (not an HA entity)
# ---------------------------------------------------------------------------

class MixOutTracker:
    """Subscribes to /volume and pushes computed secondaryVolume to device.

    Owned by Htp1MixOutTrackingSwitch; activated/deactivated via enable/disable.
    """

    def __init__(self, htp1, hass) -> None:
        self._htp1 = htp1
        self._hass = hass
        self._enabled = False
        self._unsub_volume: Callable[[], None] | None = None
        self._pending_task: asyncio.Task | None = None

    # --- parameter sources (set by the switch after entities are available) ---

    def _get_param(self, attr: str, default: float) -> float:
        return float(getattr(self._htp1, attr, default))

    # --- lifecycle ---

    def enable(self) -> None:
        if self._enabled:
            return
        self._enabled = True
        self._unsub_volume = self._htp1.subscribe("/volume", self._on_volume_update)
        # Store reference on htp1 so parameter entities can trigger recalculate().
        self._htp1.mix_out_tracker = self
        # Sync secondaryPowerOnVolume immediately when tracking is activated.
        self._sync_power_on_volume()

    def disable(self) -> None:
        self._enabled = False
        if self._unsub_volume is not None:
            try:
                self._unsub_volume()
            except Exception:
                pass
            self._unsub_volume = None
        # Cancel any pending debounced write.
        if self._pending_task is not None and not self._pending_task.done():
            self._pending_task.cancel()
        self._pending_task = None
        # Clear reference so parameter entities do not call a disabled tracker.
        if getattr(self._htp1, "mix_out_tracker", None) is self:
            self._htp1.mix_out_tracker = None

    # --- callback / recalculate ---

    def _on_volume_update(self, value=None) -> None:
        """Called by aiohtp1 on every /volume WebSocket update.

        Schedules a debounced write so rapid volume sweeps do not flood
        the device with WebSocket messages.
        """
        if not self._enabled:
            return
        asyncio.run_coroutine_threadsafe(
            self._debounced_recalculate(), self._hass.loop
        )

    async def _debounced_recalculate(self) -> None:
        """Cancel any pending write, wait DEBOUNCE_DELAY, then write."""
        if self._pending_task is not None and not self._pending_task.done():
            self._pending_task.cancel()
        self._pending_task = asyncio.ensure_future(self._delayed_write())

    async def _delayed_write(self) -> None:
        """Wait for the debounce delay then perform the actual write."""
        try:
            delay = self._get_param("mix_out_tracking_delay", 0.7)
            await asyncio.sleep(delay)
            await self._do_write()
        except asyncio.CancelledError:
            pass  # a newer update arrived before the delay elapsed

    def recalculate(self) -> None:
        """Recompute and write secondaryVolume immediately (no debounce).

        Called when a tracking parameter or the curve toggle changes — the
        user has finished adjusting, so the write should happen right away.
        Any pending debounced write from a volume update is cancelled first.
        """
        if not self._enabled:
            return

        # Cancel a pending debounced write so it does not overwrite this one.
        if self._pending_task is not None and not self._pending_task.done():
            self._pending_task.cancel()
            self._pending_task = None

        asyncio.run_coroutine_threadsafe(
            self._do_write(), self._hass.loop
        )

    async def _do_write(self) -> None:
        """Compute target and write secondaryVolume if the value changed."""
        if not self._enabled:
            return

        main = getattr(self._htp1, "volume", None)
        if main is None or main > 0:
            # Positive values are invalid (device quirk / power-on race).
            return

        offset  = self._get_param("mix_out_tracking_offset", 0.0)
        thresh  = self._get_param("mix_out_tracking_thresh", -20.0)
        boost   = self._get_param("mix_out_tracking_boost",  12.0)
        exp     = self._get_param("mix_out_tracking_exp",     1.0)
        vol_min = self._get_param("mix_out_tracking_vol_min", -60.0)
        curve_enabled = bool(getattr(self._htp1, "mix_out_tracking_curve_enabled", False))

        target = compute_mix_out_volume(
            main, offset, thresh, boost, exp, vol_min, curve_enabled
        )

        current = getattr(self._htp1, "secondary_volume", None)
        if current == target:
            return

        await self._write_volume(target)

        # Keep secondaryPowerOnVolume in sync whenever parameters change.
        self._sync_power_on_volume()

    async def _write_volume(self, target: int) -> None:
        try:
            async with self._htp1:
                self._htp1.secondary_volume = target
                await self._htp1.commit()
        except Exception:
            _LOGGER.debug("MixOutTracker: write failed", exc_info=True)

    def _sync_power_on_volume(self) -> None:
        """Compute and write secondaryPowerOnVolume from powerOnVol.

        Called when tracking is enabled or parameters change, so that the
        Mix Out power-on volume stays consistent with the tracking curve.
        """
        power_on_vol = getattr(self._htp1, "power_on_vol", None)
        if power_on_vol is None or power_on_vol > 0:
            return

        offset  = self._get_param("mix_out_tracking_offset", 0.0)
        thresh  = self._get_param("mix_out_tracking_thresh", -20.0)
        boost   = self._get_param("mix_out_tracking_boost",  12.0)
        exp     = self._get_param("mix_out_tracking_exp",     1.0)
        vol_min = self._get_param("mix_out_tracking_vol_min", -60.0)
        curve_enabled = bool(getattr(self._htp1, "mix_out_tracking_curve_enabled", False))

        target = compute_mix_out_volume(
            power_on_vol, offset, thresh, boost, exp, vol_min, curve_enabled
        )

        current = getattr(self._htp1, "secondary_poweron_volume", None)
        if current == target:
            return

        asyncio.run_coroutine_threadsafe(
            self._write_power_on_volume(target), self._hass.loop
        )

    async def _write_power_on_volume(self, target: int) -> None:
        try:
            async with self._htp1:
                self._htp1.secondary_poweron_volume = target
                await self._htp1.commit()
        except Exception:
            _LOGGER.debug("MixOutTracker: power-on volume write failed", exc_info=True)



def _trigger_recalculate(htp1) -> None:
    """Call recalculate() on the active MixOutTracker if one exists."""
    tracker = getattr(htp1, "mix_out_tracker", None)
    if tracker is not None:
        tracker.recalculate()


# ---------------------------------------------------------------------------
# Tracking switch entity
# ---------------------------------------------------------------------------

class Htp1MixOutTrackingSwitch(SwitchEntity, RestoreEntity):
    """HA switch that enables/disables mix-out volume tracking.

    State is persisted via RestoreEntity so it survives HA restarts.
    Does NOT map to any device WebSocket path.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:link-variant"
    _attr_entity_registry_enabled_default = True

    def __init__(self, htp1, entry_id: str) -> None:
        self._htp1 = htp1
        self._entry_id = entry_id
        self._tracking_on = False
        self._tracker = MixOutTracker(htp1, None)   # hass injected in async_added_to_hass

        self._attr_unique_id = f"{entry_id}_mix_out_tracking"
        self._attr_name = "Mix Out Volume Tracking"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Monoprice",
            model="HTP-1",
            name="HTP-1",
        )

        self._unsubs: list[Callable[[], None]] = []
        self._unsub_ui_lock: Callable[[], None] | None = None

    @property
    def available(self) -> bool:
        return bool(getattr(self._htp1, "connected", False))

    @property
    def is_on(self) -> bool:
        return self._tracking_on

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        # Inject hass into the tracker now that it is available.
        self._tracker._hass = self.hass

        # Restore previous state.
        last = await self.async_get_last_state()
        self._tracking_on = (last is not None and last.state == "on")
        if self._tracking_on:
            self._tracker.enable()

        # Refresh when connection state changes.
        unsub = self._htp1.subscribe("#connection", self._handle_update)
        if callable(unsub):
            self._unsubs.append(unsub)

        self._unsub_ui_lock = async_dispatcher_connect(
            self.hass, ui_lock_signal(self._entry_id), self._handle_update
        )

        schedule_entity_update_threadsafe(self)

    async def async_will_remove_from_hass(self) -> None:
        self._tracker.disable()
        for unsub in self._unsubs:
            if callable(unsub):
                try:
                    unsub()
                except Exception:
                    pass
        self._unsubs = []
        if callable(self._unsub_ui_lock):
            try:
                self._unsub_ui_lock()
            except Exception:
                pass

    async def async_turn_on(self, **kwargs) -> None:
        self._tracking_on = True
        self._tracker.enable()
        schedule_entity_update_threadsafe(self)

    async def async_turn_off(self, **kwargs) -> None:
        self._tracking_on = False
        self._tracker.disable()
        schedule_entity_update_threadsafe(self)

    def _handle_update(self, *args) -> None:
        schedule_entity_update_threadsafe(self)


# ---------------------------------------------------------------------------
# Restore-backed number entity for local (non-device) parameters
# ---------------------------------------------------------------------------

class Htp1LocalNumber(NumberEntity, RestoreEntity):
    """NumberEntity whose value is stored locally (RestoreEntity), not on device.

    Used for mix-out tracking parameters that have no HTP-1 path.
    The value is kept as a plain attribute on the htp1 object so that
    MixOutTracker can read it without importing HA helpers.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        htp1,
        entry_id: str,
        key: str,
        name: str,
        htp1_attr: str,
        min_val: float,
        max_val: float,
        step: float,
        default: float,
        unit: str = "dB",
        icon: str | None = None,
        mode: NumberMode = NumberMode.SLIDER,
    ) -> None:
        self._htp1 = htp1
        self._entry_id = entry_id
        self._key = key
        self._htp1_attr = htp1_attr
        self._default = default

        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_name = name
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_mode = mode

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Monoprice",
            model="HTP-1",
            name="HTP-1",
        )

        self._unsubs: list[Callable[[], None]] = []

    @property
    def available(self) -> bool:
        return bool(getattr(self._htp1, "connected", False))

    @property
    def native_value(self) -> float:
        return float(getattr(self._htp1, self._htp1_attr, self._default))

    async def async_set_native_value(self, value: float) -> None:
        setattr(self._htp1, self._htp1_attr, value)
        # Recalculate mix-out immediately if tracking is active.
        _trigger_recalculate(self._htp1)
        schedule_entity_update_threadsafe(self)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        # Restore persisted value or apply default.
        last = await self.async_get_last_state()
        if last is not None and last.state not in ("unknown", "unavailable", "none"):
            try:
                setattr(self._htp1, self._htp1_attr, float(last.state))
            except (ValueError, TypeError):
                setattr(self._htp1, self._htp1_attr, self._default)
        else:
            setattr(self._htp1, self._htp1_attr, self._default)

        # Refresh availability when connection changes.
        unsub = self._htp1.subscribe("#connection", self._handle_update)
        if callable(unsub):
            self._unsubs.append(unsub)

        schedule_entity_update_threadsafe(self)

    async def async_will_remove_from_hass(self) -> None:
        for unsub in self._unsubs:
            if callable(unsub):
                try:
                    unsub()
                except Exception:
                    pass
        self._unsubs = []

    def _handle_update(self, *args) -> None:
        schedule_entity_update_threadsafe(self)



# ---------------------------------------------------------------------------
# Non-linear curve enable switch
# ---------------------------------------------------------------------------

class Htp1MixOutCurveSwitch(SwitchEntity, RestoreEntity):
    """HA switch that enables/disables the non-linear tracking curve.

    When off, mix-out volume follows main volume linearly (+ offset only).
    When on, the shaped curve (thresh/boost/exp/vol_min) is applied first.
    Defaults to off. State is persisted via RestoreEntity.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:chart-bell-curve-cumulative"
    _attr_entity_registry_enabled_default = True

    def __init__(self, htp1, entry_id: str) -> None:
        self._htp1 = htp1
        self._entry_id = entry_id

        self._attr_unique_id = f"{entry_id}_mix_out_tracking_curve"
        self._attr_name = "Mix Out Tracking Non-Linear Curve"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Monoprice",
            model="HTP-1",
            name="HTP-1",
        )

        self._unsubs: list[Callable[[], None]] = []

    @property
    def available(self) -> bool:
        return bool(getattr(self._htp1, "connected", False))

    @property
    def is_on(self) -> bool:
        return bool(getattr(self._htp1, "mix_out_tracking_curve_enabled", False))

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        # Restore previous state; default is off.
        last = await self.async_get_last_state()
        enabled = (last is not None and last.state == "on")
        self._htp1.mix_out_tracking_curve_enabled = enabled

        unsub = self._htp1.subscribe("#connection", self._handle_update)
        if callable(unsub):
            self._unsubs.append(unsub)

        schedule_entity_update_threadsafe(self)

    async def async_will_remove_from_hass(self) -> None:
        for unsub in self._unsubs:
            if callable(unsub):
                try:
                    unsub()
                except Exception:
                    pass
        self._unsubs = []

    async def async_turn_on(self, **kwargs) -> None:
        self._htp1.mix_out_tracking_curve_enabled = True
        # Recalculate mix-out immediately with curve now enabled.
        _trigger_recalculate(self._htp1)
        schedule_entity_update_threadsafe(self)

    async def async_turn_off(self, **kwargs) -> None:
        self._htp1.mix_out_tracking_curve_enabled = False
        # Recalculate mix-out immediately with curve now disabled.
        _trigger_recalculate(self._htp1)
        schedule_entity_update_threadsafe(self)

    def _handle_update(self, *args) -> None:
        schedule_entity_update_threadsafe(self)

# ---------------------------------------------------------------------------
# Factory – called from switch.py / number.py async_setup_entry
# ---------------------------------------------------------------------------

# Parameter definitions: (key, name, htp1_attr, min, max, step, default, unit, icon)
_TRACKING_NUMBER_DEFS = [
    # (key, name, htp1_attr, min, max, step, default, unit, icon, mode, _reserved)
    # mode=None uses the default (SLIDER); explicit NumberMode overrides it.
    (
        "mix_out_tracking_offset",
        "Mix Out Tracking Offset",
        "mix_out_tracking_offset",
        -30.0, 30.0, 1.0, 0.0,
        "dB", "mdi:tune", None, None,
    ),
    (
        "mix_out_tracking_thresh",
        "Mix Out Tracking Threshold",
        "mix_out_tracking_thresh",
        -60.0, 0.0, 1.0, -20.0,
        "dB", "mdi:tune-variant", None, None,
    ),
    (
        "mix_out_tracking_boost",
        "Mix Out Tracking Boost",
        "mix_out_tracking_boost",
        0.0, 30.0, 1.0, 12.0,
        "dB", "mdi:arrow-up-bold", None, None,
    ),
    (
        "mix_out_tracking_exp",
        "Mix Out Tracking Curve Exponent",
        "mix_out_tracking_exp",
        0.1, 5.0, 0.1, 1.0,
        "", "mdi:chart-bell-curve", NumberMode.BOX, None,
    ),
    (
        "mix_out_tracking_vol_min",
        "Mix Out Tracking Volume Floor",
        "mix_out_tracking_vol_min",
        -80.0, -20.0, 1.0, -60.0,
        "dB", "mdi:volume-low", None, None,
    ),
    (
        "mix_out_tracking_delay",
        "Mix Out Tracking Delay",
        "mix_out_tracking_delay",
        0.1, 2.0, 0.1, 0.5,
        "s", "mdi:timer-outline", NumberMode.BOX, None,
    ),
]


def build_mix_out_tracking_switches(htp1, entry_id: str) -> list:
    """Return switch-platform entities: tracking toggle + curve toggle.

    Called from switch.py async_setup_entry.
    """
    return [
        Htp1MixOutTrackingSwitch(htp1, entry_id),
        Htp1MixOutCurveSwitch(htp1, entry_id),
    ]


def build_mix_out_tracking_numbers(htp1, entry_id: str) -> list:
    """Return number-platform entities: offset + curve parameters.

    Called from number.py async_setup_entry.
    """
    entities = []
    for (key, name, attr, mn, mx, step, default, unit, icon, mode, _prec) in _TRACKING_NUMBER_DEFS:
        kwargs = dict(
            htp1=htp1,
            entry_id=entry_id,
            key=key,
            name=name,
            htp1_attr=attr,
            min_val=mn,
            max_val=mx,
            step=step,
            default=default,
            unit=unit,
            icon=icon,
        )
        if mode is not None:
            kwargs["mode"] = mode
        entities.append(Htp1LocalNumber(**kwargs))
    return entities
