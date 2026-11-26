"""Binary sensors of the Monoprice HTP-1."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .const import DOMAIN
from .entity import htp1_device_info
from .peak import CLIP_HOLD_S, PEAK_SUBJECT


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    htp1 = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([Htp1ClippingSensor(htp1, entry.entry_id)])


class Htp1ClippingSensor(BinarySensorEntity):
    """On when an output clipped, and for CLIP_HOLD_S seconds after it.

    Disabled by default: while it is enabled and the unit is on, the
    integration reads the unit's meter feed (see peak.py).
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_registry_enabled_default = False
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_name = "Clipping"
    _attr_icon = "mdi:waveform"

    def __init__(self, htp1, entry_id: str) -> None:
        self._htp1 = htp1
        self._attr_unique_id = f"{entry_id}_clipping"
        self._attr_device_info = htp1_device_info(entry_id)
        self._unsubs: list[Callable[[], None]] = []

    @property
    def available(self) -> bool:
        return self._htp1.connected and self._htp1.peak.value is not None

    @property
    def is_on(self) -> bool | None:
        value = self._htp1.peak.value
        return None if value is None else value["clipping"]

    @property
    def extra_state_attributes(self) -> dict:
        value = self._htp1.peak.value or {}
        return {
            "channels": value.get("clip_channels") or [],
            "level": value.get("clip_level"),
            "hold_seconds": CLIP_HOLD_S,
        }

    async def async_added_to_hass(self) -> None:
        for subject in (PEAK_SUBJECT, "#connection"):
            self._unsubs.append(self._htp1.subscribe(subject, self._handle_update))
        self._htp1.peak.acquire()

    async def async_will_remove_from_hass(self) -> None:
        self._htp1.peak.release()
        for unsub in self._unsubs:
            unsub()
        self._unsubs = []

    def _handle_update(self, value=None) -> None:
        self.async_schedule_update_ha_state()
