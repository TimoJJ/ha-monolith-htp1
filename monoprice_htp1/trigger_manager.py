from __future__ import annotations

import asyncio
from typing import Callable


class TriggerManager:
    """
    Maintains trigger states locally because HTP-1 provides no feedback for AVCUI triggers.
    """

    def __init__(self, htp1) -> None:
        self._htp1 = htp1

        # IMPORTANT: must exist (your switch code reads this)
        self.states = [0, 0, 0, 0]

        # Callbacks: "#trigger1" .. "#trigger4"
        self._callbacks: dict[str, list[Callable]] = {}

        # Task handling
        self._power_task: asyncio.Task | None = None

    # ------------------------------------------------------------
    # Subscribe/notify for trigger pseudo-events
    # ------------------------------------------------------------
    def subscribe(self, subject: str, callback):
        self._callbacks.setdefault(subject, []).append(callback)

    async def _notify(self, subject: str, value=None):
        for cb in self._callbacks.get(subject, []):
            try:
                await cb(value)
            except Exception:
                pass

    async def _notify_trigger(self, index: int):
        await self._notify(f"#trigger{index+1}", self.states[index])

    async def _notify_all(self):
        for i in range(4):
            await self._notify_trigger(i)

    # ------------------------------------------------------------
    # Trigger control
    # ------------------------------------------------------------
    async def set_trigger(self, index: int, value: bool):
        self.states[index] = 1 if value else 0

        number = (
            (self.states[3] << 3)
            | (self.states[2] << 2)
            | (self.states[1] << 1)
            | self.states[0]
        )

        hex_value = format(number, "X")
        cmd = f"trigger {hex_value}"
        await self._htp1.send_avcui(cmd)

        await self._notify_trigger(index)


    async def set_local_state(self, index: int, value: bool, notify: bool = True):
        """Set trigger state locally (no AVCUI command), optionally notify HA switches."""
        self.states[index] = 1 if value else 0
        if notify:
            await self._notify_trigger(index)


    async def set_all(self, value: bool):
        for i in range(4):
            self.states[i] = 1 if value else 0

        number = (
            (self.states[3] << 3)
            | (self.states[2] << 2)
            | (self.states[1] << 1)
            | self.states[0]
        )

        hex_value = format(number, "X")
        cmd = f"trigger {hex_value}"
        await self._htp1.send_avcui(cmd)

        await self._notify_all()

    # ------------------------------------------------------------
    # Power modeled behaviour
    # ------------------------------------------------------------
    def handle_power_state(self, power_is_on: bool):
        """
        Called by trigger_switch.py when /powerIsOn changes.
        Schedules modeled trigger states.
        """
        # cancel any existing power task
        if self._power_task and not self._power_task.done():
            self._power_task.cancel()

        if power_is_on:
            self._power_task = asyncio.create_task(self._power_on_sequence())
        else:
            self._power_task = asyncio.create_task(self._power_off_sequence())

    async def _power_on_sequence(self):
        """
        Power ON -> trigger status go ON with:
        trigger1: +0.1s, trigger2: +1.1s, trigger3: +2.1s, trigger4: +3.1s
        """
        # If you want a different base delay, change this list only:
        delays = [0.1, 1.1, 2.1, 3.1]

        # We model the HTP-1 behaviour only (no AVCUI command needed here),
        # OR you can actually send the trigger command too.
        # Here we only update HA-side state because the device itself already does it.
        await asyncio.sleep(delays[0])
        self.states[0] = 1
        await self._notify_trigger(0)

        await asyncio.sleep(1)
        self.states[1] = 1
        await self._notify_trigger(1)

        await asyncio.sleep(1)
        self.states[2] = 1
        await self._notify_trigger(2)

        await asyncio.sleep(1)
        self.states[3] = 1
        await self._notify_trigger(3)

    async def _power_off_sequence(self):
        """
        Power OFF -> triggers go OFF after 1s
        """
        await asyncio.sleep(0.1)
        for i in range(4):
            self.states[i] = 0
        await self._notify_all()
