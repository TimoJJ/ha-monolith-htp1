from homeassistant.helpers.entity import Entity
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN


class Htp1Entity(Entity):
    """Base class for all HTP-1 entities."""

    def __init__(self, htp1, entry_id: str):
        self._htp1 = htp1
        self._entry_id = entry_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Monoprice",
            model="HTP-1",
            name="HTP-1",
        )

    @property
    def available(self):
        """Return connection status."""
        return self._htp1.connected
