"""Support for the Monoprice HTP-1."""

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from .aiohtp1 import Htp1
from .const import DOMAIN, LOGGER


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Monoprice HTP-1 config entry."""
    htp1 = hass.data[DOMAIN][entry.entry_id]
    async_add_entities((Htp1MediaPlayer(htp1=htp1, entry_id=entry.entry_id),), True)


class Htp1MediaPlayer(MediaPlayerEntity):
    """HTP-1 Media Player Entity."""

    def __init__(self, htp1: Htp1, entry_id: str) -> None:
        """Initialize."""
        self.htp1 = htp1

        self._power_cache = None
        self._muted_cache = None
        self._volume_cache = None

        self._attr_unique_id = f"{entry_id}_media_player"
        self._attr_name = "HTP-1"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Monoprice",
            model="HTP-1",
            name="HTP-1",
        )

    @property
    def should_poll(self) -> bool:
        """Return the polling state."""
        return False

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

        async def _on_volume(value):
            self._volume_cache = value
            self.async_schedule_update_ha_state()

        async def _on_connection(_value=None):
            # refresh cached calibration dependent values
            try:
                self._attr_volume_step = 1 / (htp1.cal_vph - htp1.cal_vpl)
            except Exception:
                self._attr_volume_step = None
            # seed caches from current state
            self._power_cache = htp1.power
            self._muted_cache = htp1.muted
            self._volume_cache = htp1.volume
            self.async_schedule_update_ha_state()

        htp1.subscribe("/muted", _on_muted)
        htp1.subscribe("/powerIsOn", _on_power)
        htp1.subscribe("/volume", _on_volume)
        htp1.subscribe("/input", _on_connection)
        htp1.subscribe("#connection", _on_connection)

        # seed caches immediately
        self._power_cache = htp1.power
        self._muted_cache = htp1.muted
        self._volume_cache = htp1.volume
        self.async_schedule_update_ha_state()


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

        async def _on_volume(value):
            self._volume_cache = value
            self.async_schedule_update_ha_state()

        async def _on_connection(_value=None):
            # refresh cached calibration dependent values
            try:
                self._attr_volume_step = 1 / (htp1.cal_vph - htp1.cal_vpl)
            except Exception:
                self._attr_volume_step = None
            # seed caches from current state
            self._power_cache = htp1.power
            self._muted_cache = htp1.muted
            self._volume_cache = htp1.volume
            self.async_schedule_update_ha_state()

        htp1.subscribe("/muted", _on_muted)
        htp1.subscribe("/powerIsOn", _on_power)
        htp1.subscribe("/volume", _on_volume)
        htp1.subscribe("/input", _on_connection)
        htp1.subscribe("#connection", _on_connection)

        # seed caches immediately
        self._power_cache = htp1.power
        self._muted_cache = htp1.muted
        self._volume_cache = htp1.volume
        self.async_schedule_update_ha_state()

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        return (
            MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.SELECT_SOUND_MODE
            | MediaPlayerEntityFeature.SELECT_SOURCE
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
        )

    ## Power

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        LOGGER.debug("async_turn_on:")
        async with self.htp1 as tx:
            tx.power = True
            await tx.commit()
        self._power_cache = True
        self.async_schedule_update_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        LOGGER.debug("async_turn_off:")
        async with self.htp1 as tx:
            tx.power = False
            await tx.commit()
        self._power_cache = False
        self.async_schedule_update_ha_state()

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the player."""
        pwr = self._power_cache if self._power_cache is not None else self.htp1.power
        if pwr is True or pwr == 1:
            return MediaPlayerState.ON
        if pwr is False or pwr == 0:
            return MediaPlayerState.OFF
        return None

    ## Volume

    @property
    def volume_step(self) -> float | None:
        """Return the volume step for volume_up/down (0..1)."""
        try:
            # 1 dB step mapped to 0..1 volume scale
            return 1 / (self.htp1.cal_vph - self.htp1.cal_vpl)
        except Exception:
            return None


    @property
    def volume_level(self):
        """Return the volume level of the media player (0..1)."""
        volume = self._volume_cache if self._volume_cache is not None else self.htp1.volume
        return (volume - self.htp1.cal_vpl) / (self.htp1.cal_vph - self.htp1.cal_vpl)



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
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        return self._muted_cache if self._muted_cache is not None else self.htp1.muted

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the entity."""
        async with self.htp1 as tx:
            tx.muted = mute
            await tx.commit()

    ## Sound Mode

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        async with self.htp1 as tx:
            tx.upmix = sound_mode
            await tx.commit()

    @property
    def sound_mode(self):
        """Return the current sound mode."""
        return self.htp1.upmix

    @property
    def sound_mode_list(self):
        """Return a list of available sound modes."""
        return self.htp1.upmixes

    ## Source

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        async with self.htp1 as tx:
            tx.input = source
            await tx.commit()

    @property
    def source_id(self):
        """ID of the current input source."""
        return self.htp1.input

    @property
    def source(self):
        """Name of the current input source."""
        return self.htp1.input

    @property
    def source_list(self):
        """List of available input sources."""
        return self.htp1.inputs
