from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

TRIGGER_NAMES = [
    "Trigger 1",
    "Trigger 2",
    "Trigger 3",
    "Trigger 4",
]


class TriggerSwitch(SwitchEntity, RestoreEntity):
    """HTP-1 trigger switch."""

    _attr_has_entity_name = True

    def __init__(self, htp1, entry_id: str, index: int):
        self._htp1 = htp1
        self._index = index

        self._attr_unique_id = f"{entry_id}_trigger_{index + 1}"
        self._attr_name = TRIGGER_NAMES[index]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Monoprice",
            model="HTP-1",
            name="HTP-1",
        )

    async def async_added_to_hass(self):
        self._unsubs = []
        await super().async_added_to_hass()

        # Restore last known state across HA/integration restarts.
        last_state = await self.async_get_last_state()
        if last_state is not None:
            await self._htp1.trigger.set_local_state(
                self._index,
                last_state.state == "on",
                notify=False,
            )
            self.async_schedule_update_ha_state()

        # Update trigger switch when manager notifies.
        unsub = self._htp1.trigger.subscribe(
            f"#trigger{self._index + 1}", self._handle_trigger_update
        )
        if callable(unsub):
            self._unsubs.append(unsub)

        # Listen to power state changes only once (avoid duplicates).
        if self._index == 0:
            unsub = self._htp1.subscribe("/powerIsOn", self._handle_power_update)
            if callable(unsub):
                self._unsubs.append(unsub)

    async def async_will_remove_from_hass(self) -> None:
        for unsub in getattr(self, "_unsubs", []):
            if callable(unsub):
                try:
                    unsub()
                except Exception:
                    pass

    def _handle_trigger_update(self, value):
        self.async_schedule_update_ha_state()

    def _handle_power_update(self, value):
        power = bool(value)
        try:
            self._htp1.trigger.handle_power_state(power)
        except Exception:
            _LOGGER.debug("Failed to handle power update for triggers", exc_info=True)

    @property
    def available(self) -> bool:
        return self._htp1.connected

    @property
    def is_on(self) -> bool:
        return bool(self._htp1.trigger.states[self._index])

    async def async_turn_on(self, **kwargs):
        await self._htp1.trigger.set_trigger(self._index, True)
        # TriggerManager notifies back; no extra state write needed.

    async def async_turn_off(self, **kwargs):
        await self._htp1.trigger.set_trigger(self._index, False)
        # TriggerManager notifies back; no extra state write needed.


def build_trigger_switches(htp1, entry_id: str):
    return [TriggerSwitch(htp1, entry_id, i) for i in range(4)]
