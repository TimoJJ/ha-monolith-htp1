from __future__ import annotations

import logging
from typing import Callable

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, ui_lock_signal
from .helpers import schedule_entity_update_threadsafe

_LOGGER = logging.getLogger(__name__)

TRIGGER_NAMES = [
    "Trigger 1",
    "Trigger 2",
    "Trigger 3",
    "Trigger 4",
]


class TriggerSwitch(SwitchEntity):
    """HTP-1 amp trigger output.

    The state is the real output state the device publishes at
    /triggers/N/on (firmware 2.2.0+). Without that path the switch is unavailable.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, htp1, entry_id: str, index: int):
        self._htp1 = htp1
        self._entry_id = entry_id
        self._index = index

        self._attr_unique_id = f"{entry_id}_trigger_{index + 1}"
        self._attr_name = TRIGGER_NAMES[index]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Monoprice",
            model="HTP-1",
            name="HTP-1",
        )

        self._unsubs: list[Callable[[], None]] = []

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        if self._index == 0 and self._htp1.connected and self._htp1.trigger_on(0) is None:
            _LOGGER.warning(
                "The HTP-1 does not report amp trigger states; "
                "trigger switches need firmware 2.2.0 or newer"
            )

        for subject in (f"/triggers/{self._index}/on", "/powerIsOn", "#connection"):
            unsub = self._htp1.subscribe(subject, self._handle_update)
            if callable(unsub):
                self._unsubs.append(unsub)

        self._unsub_ui_lock = async_dispatcher_connect(
            self.hass, ui_lock_signal(self._entry_id), self._handle_update
        )

    async def async_will_remove_from_hass(self) -> None:
        for unsub in self._unsubs:
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

    def _locked_by_standby(self) -> bool:
        # The device ignores trigger switching in standby.
        if getattr(self._htp1, "lock_controls_when_off", True):
            pwr = getattr(self._htp1, "power", None)
            return pwr is False or pwr == 0
        return False

    @property
    def available(self) -> bool:
        if not self._htp1.connected:
            return False
        if self._htp1.trigger_on(self._index) is None:
            return False
        return not self._locked_by_standby()

    @property
    def is_on(self) -> bool | None:
        return self._htp1.trigger_on(self._index)

    async def _set(self, value: bool) -> None:
        # Enforce the standby lock even if called via service.
        if self._locked_by_standby():
            return

        async with self._htp1:
            self._htp1.set_trigger_on(self._index, value)
            await self._htp1.commit()

        # The device reports the real state back; re-read in case it refused.
        schedule_entity_update_threadsafe(self)

    async def async_turn_on(self, **kwargs):
        await self._set(True)

    async def async_turn_off(self, **kwargs):
        await self._set(False)


def build_trigger_switches(htp1, entry_id: str):
    return [TriggerSwitch(htp1, entry_id, i) for i in range(4)]
