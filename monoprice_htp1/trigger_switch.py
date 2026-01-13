from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity  # <-- LISaYS
from .const import DOMAIN


TRIGGER_NAMES = [
    "Trigger 1",
    "Trigger 2",
    "Trigger 3",
    "Trigger 4",
]


class TriggerSwitch(SwitchEntity, RestoreEntity):  # <-- MUUTOS
    """HTP-1 trigger switch."""

    _attr_has_entity_name = True

    def __init__(self, htp1, entry_id: str, index: int):
        self._htp1 = htp1
        self._index = index

        self._attr_unique_id = f"{entry_id}_trigger_{index+1}"
        self._attr_name = TRIGGER_NAMES[index]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Monoprice",
            model="HTP-1",
            name="HTP-1",
        )

    async def async_added_to_hass(self):
        await super().async_added_to_hass()  # <-- LISaYS

        # Restore last known state across HA/integration restarts
        last_state = await self.async_get_last_state()  # <-- LISaYS
        if last_state is not None:
            await self._htp1.trigger.set_local_state(
                self._index,
                last_state.state == "on",
                notify=False,
            )
            self.async_write_ha_state()

        # update trigger switch when manager notifies
        self._htp1.trigger.subscribe(
            f"#trigger{self._index+1}", self._handle_trigger_update
        )

        # Listen to power state changes only once (avoid duplicates)
        if self._index == 0:
            self._htp1.subscribe("/powerIsOn", self._handle_power_update)

    async def _handle_trigger_update(self, value):
        self.async_write_ha_state()

    async def _handle_power_update(self, value):
        power = bool(value)
        self._htp1.trigger.handle_power_state(power)

    @property
    def available(self):
        return self._htp1.connected

    @property
    def is_on(self) -> bool:
        return bool(self._htp1.trigger.states[self._index])

    async def async_turn_on(self, **kwargs):
        await self._htp1.trigger.set_trigger(self._index, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        await self._htp1.trigger.set_trigger(self._index, False)
        self.async_write_ha_state()


def build_trigger_switches(htp1, entry_id: str):
    return [TriggerSwitch(htp1, entry_id, i) for i in range(4)]
