from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


def htp1_device_info(entry_id: str) -> DeviceInfo:
    """Device info shared by every HTP-1 entity, so the device has one name."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        manufacturer="Monoprice",
        model="HTP-1",
        name="HTP-1",
    )
