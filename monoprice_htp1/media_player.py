"""Support for the Monoprice HTP-1."""

from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .aiohtp1 import Htp1
from .const import DOMAIN, LOGGER


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Monoprice HTP-1 config entry."""
    htp1: Htp1 = hass.data[DOMAIN][entry.entry_id]
    async_add_entities((Htp1MediaPlayer(htp1=htp1, entry_id=entry.entry_id),), True)


class Htp1MediaPlayer(MediaPlayerEntity):
    """HTP-1 Media Player Entity."""

    def __init__(self, htp1: Htp1, entry_id: str) -> None:
        """Initialize."""
        self.htp1 = htp1

        self._power_cache: bool | None = None
        self._muted_cache: bool | None = None
        self._volume_cache: int | float | None = None

        self._attr_unique_id = f"{entry_id}_media_player"
        self._attr_name = "HTP-1"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Monoprice",
            model="HTP-1",
            name="HTP-1",
        )

        # Will be updated on (re)connect.
        self._attr_volume_step: float | None = None

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def available(self) -> bool:
        """Return connection status."""
        return self.htp1.connected

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        await super().async_added_to_hass()

        htp1 = self.htp1

        async def _on_power(value):
            self._power_cache = value
            self.async_schedule_update_ha_state()

        async def _on_muted(value):
            self._muted_cache = value
            self.async_schedule_update_ha_state()

        async def _on_upmix(_value):
            self.async_schedule_update_ha_state()

        async def _on_volume(value):
            self._volume_cache = value
            self.async_schedule_update_ha_state()

        async def _on_connection(_value=None):
            # When disconnected, clear caches so we don't keep showing stale values
            # (e.g. power ON after the device reboots).
            if not htp1.connected:
                self._power_cache = None
                self._muted_cache = None
                self._volume_cache = None
                self._attr_volume_step = None
                self.async_schedule_update_ha_state()
                return

            # Refresh cached calibration dependent values
            try:
                self._attr_volume_step = 1 / (htp1.cal_vph - htp1.cal_vpl)
            except Exception:
                self._attr_volume_step = None

            # Seed caches from current state
            self._power_cache = htp1.power
            self._muted_cache = htp1.muted
            self._volume_cache = htp1.volume
            self.async_schedule_update_ha_state()

        htp1.subscribe("/muted", _on_muted)
        htp1.subscribe("/powerIsOn", _on_power)
        htp1.subscribe("/volume", _on_volume)
        # Some settings changes can imply state changes; treat them as a resync trigger.
        htp1.subscribe("/input", _on_connection)
        htp1.subscribe("#connection", _on_connection)
        htp1.subscribe("/upmix/select", _on_upmix)
        # Seed once on add.
        await _on_connection()

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        return (
            MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.SELECT_SOUND_MODE
            | MediaPlayerEntityFeature.SELECT_SOURCE
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
        )

    # Power

    async def async_turn_on(self) -> None:
        LOGGER.debug("async_turn_on:")
        async with self.htp1 as tx:
            tx.power = True
            await tx.commit()
        self._power_cache = True
        self.async_schedule_update_ha_state()

    async def async_turn_off(self) -> None:
        LOGGER.debug("async_turn_off:")
        async with self.htp1 as tx:
            tx.power = False
            await tx.commit()
        self._power_cache = False
        self.async_schedule_update_ha_state()

    @property
    def state(self) -> MediaPlayerState | None:
        # If we're offline and caches were cleared, show unknown.
        pwr = self._power_cache if self._power_cache is not None else self.htp1.power
        if pwr is True or pwr == 1:
            return MediaPlayerState.ON
        if pwr is False or pwr == 0:
            return MediaPlayerState.OFF
        return None

    # Volume

    @property
    def volume_step(self) -> float | None:
        return self._attr_volume_step

    @property
    def volume_level(self) -> float | None:
        """Return the volume level of the media player (0..1)."""
        try:
            volume = self._volume_cache if self._volume_cache is not None else self.htp1.volume
            if volume is None:
                return None
            cal_vpl = self.htp1.cal_vpl
            cal_vph = self.htp1.cal_vph
            span = cal_vph - cal_vpl
            if span <= 0:
                return None
            return (float(volume) - cal_vpl) / span
        except Exception:
            return None

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level of the media player (0..1). Sends integer dB to HTP-1."""
        volume = max(0.0, min(1.0, float(volume)))

        cal_vpl = self.htp1.cal_vpl
        cal_vph = self.htp1.cal_vph
        span = cal_vph - cal_vpl
        if span <= 0:
            return

        target_db = cal_vpl + (volume * span)
        target_db = int(round(target_db))
        target_db = max(int(cal_vpl), min(int(cal_vph), target_db))

        async with self.htp1:
            self.htp1.volume = target_db
            await self.htp1.commit()

    @property
    def is_volume_muted(self) -> bool | None:
        val = self._muted_cache if self._muted_cache is not None else self.htp1.muted
        if val in (True, False):
            return bool(val)
        return None

    async def async_mute_volume(self, mute: bool) -> None:
        async with self.htp1 as tx:
            tx.muted = mute
            await tx.commit()

    # Sound Mode

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        async with self.htp1 as tx:
            tx.upmix = sound_mode
            await tx.commit()
        self.async_schedule_update_ha_state()

    @property
    def sound_mode(self) -> str | None:
        try:
            return self.htp1.upmix
        except Exception:
            return None

    @property
    def sound_mode_list(self) -> list[str]:
        try:
            return self.htp1.upmixes
        except Exception:
            return []

    # Source

    async def async_select_source(self, source: str) -> None:
        async with self.htp1 as tx:
            tx.input = source
            await tx.commit()

    @property
    def source(self) -> str | None:
        try:
            return self.htp1.input
        except Exception:
            return None

    @property
    def source_list(self) -> list[str]:
        try:
            return self.htp1.inputs
        except Exception:
            return []
