from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class Htp1Entity(Entity):
    """Base class for all HTP-1 entities."""

    _attr_has_entity_name = True

    def __init__(self, htp1, entry_id: str) -> None:
        self._htp1 = htp1
        self._entry_id = entry_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Monoprice",
            model="HTP-1",
            name="HTP-1",
        )

    @property
    def available(self) -> bool:
        """Return connection status."""
        return self._htp1.connected
