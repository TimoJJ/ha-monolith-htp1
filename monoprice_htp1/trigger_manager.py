from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Callable

_LOGGER = logging.getLogger(__name__)


class TriggerManager:
    """
    Maintains trigger states locally because HTP-1 provides no feedback for AVCUI triggers.
    """

    def __init__(self, htp1) -> None:
        self._htp1 = htp1

        # IMPORTANT: must exist (trigger_switch reads this)
        self.states = [0, 0, 0, 0]

        # Callbacks: "#trigger1" .. "#trigger4"
        self._callbacks: dict[str, list[Callable]] = {}

        # Task handling
        self._power_task: asyncio.Task | None = None
        self._power_gen: int = 0  # generation token to prevent stale tasks from updating state

    # ------------------------------------------------------------
    # Subscribe/notify for trigger pseudo-events
    # ------------------------------------------------------------
    def subscribe(self, subject: str, callback):
        callbacks = self._callbacks.setdefault(subject, [])
        callbacks.append(callback)

        def unsubscribe():
            try:
                callbacks.remove(callback)
            except ValueError:
                pass

        return unsubscribe

    async def _notify(self, subject: str, value=None):
        for cb in self._callbacks.get(subject, []):
            try:
                res = cb(value)
                if inspect.isawaitable(res):
                    await res
            except Exception:
                _LOGGER.debug("Trigger callback failed for %s", subject, exc_info=True)

    async def _notify_trigger(self, index: int):
        await self._notify(f"#trigger{index + 1}", self.states[index])

    async def _notify_all(self):
        for i in range(4):
            await self._notify_trigger(i)

    # ------------------------------------------------------------
    # Trigger control
    # ------------------------------------------------------------
    def _valid_index(self, index: int) -> bool:
        return 0 <= index < 4

    async def set_trigger(self, index: int, value: bool):
        if not self._valid_index(index):
            _LOGGER.debug("Invalid trigger index: %s", index)
            return

        self.states[index] = 1 if value else 0

        number = (
            (self.states[3] << 3)
            | (self.states[2] << 2)
            | (self.states[1] << 1)
            | self.states[0]
        )

        hex_value = format(number, "X")
        cmd = f"trigger {hex_value}"

        try:
            await self._htp1.send_avcui(cmd)
        except Exception:
            _LOGGER.debug("Failed to send AVCUI trigger command: %s", cmd, exc_info=True)
            return

        await self._notify_trigger(index)

    async def set_local_state(self, index: int, value: bool, notify: bool = True):
        """Set trigger state locally (no AVCUI command), optionally notify HA switches."""
        if not self._valid_index(index):
            _LOGGER.debug("Invalid trigger index: %s", index)
            return

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

        try:
            await self._htp1.send_avcui(cmd)
        except Exception:
            _LOGGER.debug("Failed to send AVCUI trigger command: %s", cmd, exc_info=True)
            return

        await self._notify_all()

    # ------------------------------------------------------------
    # Power modeled behaviour
    # ------------------------------------------------------------
    def handle_power_state(self, power_is_on: bool):
        """
        Called by trigger_switch.py when /powerIsOn changes.
        Schedules modeled trigger states.
        """
        # Bump generation; any older tasks must stop updating state.
        self._power_gen += 1
        gen = self._power_gen

        # Cancel any existing power task
        if self._power_task and not self._power_task.done():
            self._power_task.cancel()

        if power_is_on:
            self._power_task = asyncio.create_task(self._power_on_sequence(gen))
        else:
            self._power_task = asyncio.create_task(self._power_off_sequence(gen))

    async def _power_on_sequence(self, gen: int):
        """
        Power ON -> trigger status go ON with:
        trigger1: +0.1s, trigger2: +1.1s, trigger3: +2.1s, trigger4: +3.1s
        """
        # If you want a different base delay, change this list only:
        delays = [0.1, 1.1, 2.1, 3.1]

        try:
            await asyncio.sleep(delays[0])
            if gen != self._power_gen:
                return
            self.states[0] = 1
            await self._notify_trigger(0)

            await asyncio.sleep(1)
            if gen != self._power_gen:
                return
            self.states[1] = 1
            await self._notify_trigger(1)

            await asyncio.sleep(1)
            if gen != self._power_gen:
                return
            self.states[2] = 1
            await self._notify_trigger(2)

            await asyncio.sleep(1)
            if gen != self._power_gen:
                return
            self.states[3] = 1
            await self._notify_trigger(3)

        except asyncio.CancelledError:
            return
        except Exception:
            _LOGGER.debug("Power ON modeled trigger sequence failed", exc_info=True)

    async def _power_off_sequence(self, gen: int):
        """
        Power OFF -> triggers go OFF after 0.1s
        """
        try:
            await asyncio.sleep(0.1)
            if gen != self._power_gen:
                return

            for i in range(4):
                self.states[i] = 0
            await self._notify_all()

        except asyncio.CancelledError:
            return
        except Exception:
            _LOGGER.debug("Power OFF modeled trigger sequence failed", exc_info=True)
