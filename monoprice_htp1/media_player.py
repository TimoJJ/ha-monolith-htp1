"""Support for the Monoprice HTP-1."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import beq
from .aiohtp1 import Htp1
from .const import DOMAIN, LOGGER, ui_lock_signal
from .helpers import schedule_entity_update_threadsafe

# Raw device values -> UI labels
UPMIX_RAW_TO_UI = {
    "off": "Direct",
    "native": "Native",
    "dolby": "Dolby Surround",
    "dts": "DTS Neural:X",
    "auro": "Auro-3D",
    "mono": "Mono",
    "stereo": "Stereo",
}
# UI labels -> raw device values
UPMIX_UI_TO_RAW = {v: k for k, v in UPMIX_RAW_TO_UI.items()}


SERVICE_LOAD_BEQ = "load_beq_filter"
SERVICE_CLEAR_BEQ = "clear_beq_filter"

LOAD_BEQ_SCHEMA = {
    vol.Optional("title"): cv.string,
    vol.Optional("tmdb_id"): cv.string,
    vol.Optional("year"): vol.Coerce(int),
    vol.Optional("codec"): cv.string,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Monoprice HTP-1 config entry."""
    htp1: Htp1 = hass.data[DOMAIN][entry.entry_id]
    async_add_entities((Htp1MediaPlayer(htp1=htp1, entry_id=entry.entry_id),), True)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_LOAD_BEQ,
        LOAD_BEQ_SCHEMA,
        "async_load_beq_filter",
    )
    platform.async_register_entity_service(
        SERVICE_CLEAR_BEQ,
        {},
        "async_clear_beq_filter",
    )


class Htp1MediaPlayer(MediaPlayerEntity):
    """HTP-1 Media Player Entity."""

    _attr_has_entity_name = True

    def _on_ui_lock(self, _value=None):
        schedule_entity_update_threadsafe(self)

    def __init__(self, htp1: Htp1, entry_id: str) -> None:
        self._htp1 = htp1

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

        self._attr_volume_step: float | None = None
        self._unsubs: list[object] = []

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def available(self) -> bool:
        return self._htp1.connected

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        # Re-render features immediately when UI lock changes.
        self.async_on_remove(
            async_dispatcher_connect(self.hass, ui_lock_signal(self._attr_unique_id.split('_media_player', 1)[0]), self._on_ui_lock)
        )

        htp1 = self._htp1

        def _on_power(value):
            self._power_cache = bool(value) if value in (0, 1, True, False) else None
            schedule_entity_update_threadsafe(self)

        def _on_muted(value):
            self._muted_cache = bool(value) if value in (0, 1, True, False) else None
            schedule_entity_update_threadsafe(self)

        def _on_volume(value):
            self._volume_cache = value
            schedule_entity_update_threadsafe(self)

        def _on_upmix(_value):
            schedule_entity_update_threadsafe(self)

        def _on_connection(_value=None):
            if not htp1.connected:
                # Clear caches on disconnect to avoid stale UI.
                self._power_cache = None
                self._muted_cache = None
                self._volume_cache = None
                self._attr_volume_step = None
                schedule_entity_update_threadsafe(self)
                return

            try:
                # HTP-1 uses a fixed 1 dB volume step
                span = htp1.cal_vph - htp1.cal_vpl
                self._attr_volume_step = (1.0 / span) if span > 0 else None
            except Exception:
                LOGGER.debug("Failed to compute volume_step", exc_info=True)
                self._attr_volume_step = None

            # Seed caches from current state
            self._power_cache = htp1.power if htp1.power in (0, 1, True, False) else None
            self._muted_cache = htp1.muted if htp1.muted in (0, 1, True, False) else None
            self._volume_cache = htp1.volume
            schedule_entity_update_threadsafe(self)

        # Subscribe. If subscribe() returns an unsubscribe callable/object, keep it.
        def _sub(path, cb):
            try:
                ret = htp1.subscribe(path, cb)
                if ret is not None:
                    self._unsubs.append(ret)
            except Exception:
                LOGGER.debug("Subscribe failed for %s", path, exc_info=True)

        _sub("/muted", _on_muted)
        _sub("/powerIsOn", _on_power)
        _sub("/volume", _on_volume)

        # Treat input changes and explicit connection events as resync triggers.
        _sub("/input", _on_connection)
        _sub("#connection", _on_connection)

        _sub("/upmix/select", _on_upmix)

        # Seed once on add.
        _on_connection()

        # Best-effort cleanup if subscribe() returns unsubscribe callables.
        def _cleanup():
            for u in self._unsubs:
                try:
                    if callable(u):
                        u()
                except Exception:
                    pass
            self._unsubs.clear()

        self.async_on_remove(_cleanup)

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        base = MediaPlayerEntityFeature.TURN_OFF | MediaPlayerEntityFeature.TURN_ON

        # When UI lock is enabled and device is in standby, expose only power controls.
        if getattr(self._htp1, "lock_controls_when_off", True) and self._htp1.power is False:
            return base

        return (
            base
            | MediaPlayerEntityFeature.SELECT_SOUND_MODE
            | MediaPlayerEntityFeature.SELECT_SOURCE
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
        )

    # Power

    async def async_turn_on(self) -> None:
        LOGGER.debug("async_turn_on")
        async with self._htp1 as tx:
            tx.power = True
            await tx.commit()
        self._power_cache = True
        schedule_entity_update_threadsafe(self)

    async def async_turn_off(self) -> None:
        LOGGER.debug("async_turn_off")
        async with self._htp1 as tx:
            tx.power = False
            await tx.commit()
        self._power_cache = False
        schedule_entity_update_threadsafe(self)

    @property
    def state(self) -> MediaPlayerState | None:
        # When offline, avoid reading stale values from the client.
        if not self.available:
            return None

        pwr = self._power_cache if self._power_cache is not None else self._htp1.power
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
        if not self.available:
            return None

        try:
            volume = self._volume_cache if self._volume_cache is not None else self._htp1.volume
            if volume is None:
                return None

            cal_vpl = float(self._htp1.cal_vpl)
            cal_vph = float(self._htp1.cal_vph)
            span = cal_vph - cal_vpl
            if span <= 0:
                return None

            return (float(volume) - cal_vpl) / span
        except Exception:
            LOGGER.debug("Failed to compute volume_level", exc_info=True)
            return None

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level of the media player (0..1). Sends integer dB to HTP-1."""
        if not self.available:
            return

        volume = max(0.0, min(1.0, float(volume)))

        try:
            cal_vpl = float(self._htp1.cal_vpl)
            cal_vph = float(self._htp1.cal_vph)
            span = cal_vph - cal_vpl
            if span <= 0:
                return

            target_db = cal_vpl + (volume * span)
            target_db = int(round(target_db))
            target_db = max(int(cal_vpl), min(int(cal_vph), target_db))
        except Exception:
            LOGGER.debug("Failed to compute target dB from volume level", exc_info=True)
            return

        async with self._htp1:
            self._htp1.volume = target_db
            await self._htp1.commit()

    @property
    def is_volume_muted(self) -> bool | None:
        if not self.available:
            return None
        val = self._muted_cache if self._muted_cache is not None else self._htp1.muted
        if val in (True, False):
            return bool(val)
        return None

    async def async_mute_volume(self, mute: bool) -> None:
        if not self.available:
            return
        async with self._htp1 as tx:
            tx.muted = mute
            await tx.commit()

    # Sound Mode

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        if not self.available:
            return

        # Convert UI label -> raw device value (fall back to raw if already raw)
        raw = UPMIX_UI_TO_RAW.get(sound_mode, sound_mode)

        async with self._htp1 as tx:
            tx.upmix = raw
            await tx.commit()

        schedule_entity_update_threadsafe(self)

    @property
    def sound_mode(self) -> str | None:
        if not self.available:
            return None
        try:
            raw = self._htp1.upmix
            if raw is None:
                return None
            return UPMIX_RAW_TO_UI.get(raw, raw)
        except Exception:
            LOGGER.debug("Failed to read sound_mode", exc_info=True)
            return None

    @property
    def sound_mode_list(self) -> list[str]:
        if not self.available:
            return []
        try:
            raws = self._htp1.upmixes or []
            return [UPMIX_RAW_TO_UI.get(raw, raw) for raw in raws]
        except Exception:
            LOGGER.debug("Failed to read sound_mode_list", exc_info=True)
            return []

    # Source

    async def async_select_source(self, source: str) -> None:
        if not self.available:
            return
        async with self._htp1 as tx:
            tx.input = source
            await tx.commit()

    @property
    def source(self) -> str | None:
        if not self.available:
            return None
        try:
            return self._htp1.input
        except Exception:
            LOGGER.debug("Failed to read source", exc_info=True)
            return None

    @property
    def source_list(self) -> list[str]:
        if not self.available:
            return []
        try:
            return self._htp1.inputs
        except Exception:
            LOGGER.debug("Failed to read source_list", exc_info=True)
            return []

    # BEQ Services

    async def async_load_beq_filter(
        self,
        title: str | None = None,
        tmdb_id: str | None = None,
        year: int | None = None,
        codec: str | None = None,
    ) -> None:
        """Search the BEQ catalogue and load a bass correction filter."""
        if not title and not tmdb_id:
            raise HomeAssistantError(
                "Either 'title' or 'tmdb_id' must be provided"
            )

        if not self.available:
            raise HomeAssistantError("HTP-1 is not connected")

        session = async_get_clientsession(self.hass)
        catalogue = await beq.async_fetch_catalogue(session)

        if not catalogue:
            raise HomeAssistantError("Failed to fetch BEQ catalogue")

        if tmdb_id:
            tmdb_int = beq.parse_tmdb_id(tmdb_id)
            if tmdb_int is None:
                raise HomeAssistantError(f"Invalid TMDB ID: {tmdb_id}")
            results = beq.search_by_tmdb_id(catalogue, tmdb_int, codec=codec)
        else:
            results = beq.search_by_title(
                catalogue, title, year=year, codec=codec
            )

        if not results:
            search_desc = f"TMDB ID {tmdb_id}" if tmdb_id else f"'{title}'"
            if year:
                search_desc += f" ({year})"
            if codec:
                search_desc += f" [{codec}]"
            raise HomeAssistantError(
                f"No BEQ filter found for {search_desc}"
            )

        entry = beq.best_match(results)
        filters = beq.prepare_filters(entry)
        entry_title = entry.get("title", "Unknown")

        if not filters:
            raise HomeAssistantError(
                f"BEQ entry '{entry_title}' has no filters"
            )

        LOGGER.info(
            "Loading BEQ filter: %s (%d filters, %d matches found)",
            entry_title,
            len(filters),
            len(results),
        )

        success = await self._htp1.load_beq(entry_title, filters)
        if not success:
            raise HomeAssistantError("Failed to load BEQ filter on device")

    async def async_clear_beq_filter(self) -> None:
        """Clear the currently loaded BEQ filter."""
        if not self.available:
            raise HomeAssistantError("HTP-1 is not connected")

        success = await self._htp1.clear_beq()
        if not success:
            raise HomeAssistantError("Failed to clear BEQ filter on device")
