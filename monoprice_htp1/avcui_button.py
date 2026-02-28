from __future__ import annotations

import logging
from typing import Callable

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, ui_lock_signal
from .helpers import schedule_entity_update_threadsafe

_LOGGER = logging.getLogger(__name__)


def build_avcui_button_entities(htp1, entry_id: str):
    # Keep this extensible in case more AVCUI buttons are added later
    return [
        Htp1AvcuiButton(
            htp1=htp1,
            entry_id=entry_id,
            key="hpe",
            name="HDMI Reset",
            command="hpe",
            icon="mdi:button-pointer",
        )
    ]


class Htp1AvcuiButton(ButtonEntity):
    """Stateless AVCUI command button."""

    _attr_has_entity_name = True

    def __init__(
        self,
        htp1,
        entry_id: str,
        key: str,
        name: str,
        command: str,
        icon: str | None = None,
    ) -> None:
        self._htp1 = htp1
        self._entry_id = entry_id
        self._command = command

        self._attr_unique_id = f"{entry_id}_avcui_btn_{key}"
        self._attr_name = name
        self._attr_icon = icon

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Monoprice",
            model="HTP-1",
            name="HTP-1",
        )

        # Store unsubscribe callables for htp1 subscriptions
        self._unsubs: list[Callable[[], None]] = []

    @property
    def available(self) -> bool:
        if not self._htp1.connected:
            return False

        # When UI lock is enabled, disable AVCUI buttons while device is off/standby.
        if getattr(self._htp1, "lock_controls_when_off", True):
            pwr = getattr(self._htp1, "power", None)
            if pwr is False or pwr == 0:
                return False

        return True

    async def async_added_to_hass(self) -> None:
        # Update state when UI lock changes
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, ui_lock_signal(self._entry_id), self._handle_ui_lock
            )
        )

        # Also update availability when power or connection changes.
        # Otherwise the button can remain "unavailable" after standby->on transitions.
        self._subscribe("/powerIsOn")
        self._subscribe("#connection")

    async def async_will_remove_from_hass(self) -> None:
        for unsub in self._unsubs:
            try:
                unsub()
            except Exception:
                pass
        self._unsubs = []

    def _subscribe(self, path: str) -> None:
        try:
            unsub = self._htp1.subscribe(path, self._handle_state_change)
            if callable(unsub):
                self._unsubs.append(unsub)
        except Exception:
            _LOGGER.debug("Subscribe failed for %s", path, exc_info=True)

    def _handle_state_change(self, _value=None) -> None:
        schedule_entity_update_threadsafe(self)

    def _handle_ui_lock(self, _value=None) -> None:
        schedule_entity_update_threadsafe(self)

    async def async_press(self) -> None:
        try:
            await self._htp1.send_avcui(self._command)
        except Exception:
            _LOGGER.error(
                "Failed to send AVCUI command '%s'", self._command, exc_info=True
            )
            return

        # Force UI refresh in case availability or diagnostics depend on this
        schedule_entity_update_threadsafe(self)
