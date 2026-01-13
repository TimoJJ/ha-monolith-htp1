from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN


SENSOR_DEFINITIONS = [
    {
        "key": "power",
        "name": "Power",
        "path": "/powerIsOn",
        "value_fn": lambda htp1: STATE_ON if htp1.power else STATE_OFF,
        "icon": "mdi:power",        
    },
    {
        "key": "volume",
        "name": "Volume",
        "path": "/volume",
        "value_fn": lambda htp1: htp1.volume,
        "native_unit_of_measurement": "dB",       
        "device_class": "sound_pressure",         
        "state_class": "measurement",
        "icon": "mdi:volume-high",        
    },
    {
        "key": "secondvolume",
        "name": "Secondary Volume mso",
        "path": "/secondVolume",
        "value_fn": lambda htp1: htp1.secondvolume,
        "native_unit_of_measurement": "dB",       
        "device_class": "sound_pressure",         
        "state_class": "measurement",
        "icon": "mdi:volume-high",        
        "entity_registry_enabled_default": False,
    },
    {
        "key": "mute",
        "name": "Mute",
        "path": "/muted",
        "value_fn": lambda htp1: STATE_ON if htp1.muted else STATE_OFF,
        "icon": "mdi:volume-off",                   
    },
    {
        "key": "input",
        "name": "Input",
        "path": "/input",
        "value_fn": lambda htp1: htp1.input,
        "icon": "mdi:format-list-bulleted",
    },
    {
        "key": "upmix",
        "name": "Upmix",
        "path": "/upmix/select",
        "value_fn": lambda htp1: htp1.upmix,
        "icon": "mdi:arrow-expand-up",
    },
    {
        "key": "bass_level",
        "name": "Bass Level",
        "path": "/eq/bass/level",
        "value_fn": lambda htp1: htp1.bass_level,
        "native_unit_of_measurement": "dB",       
        "device_class": "sound_pressure",         
        "state_class": "measurement",             
        "icon": "mdi:knob",                   
    },
    {
        "key": "bass_frequency",
        "name": "Bass Corner Frequency",
        "path": "/eq/bass/freq",
        "value_fn": lambda htp1: htp1.bass_frequency,
        "native_unit_of_measurement": "Hz",        
        "device_class": "frequency",               
        "state_class": "measurement",              
        "icon": "mdi:sine-wave",                   
    },
    {
        "key": "treble_level",
        "name": "Treble Level",
        "path": "/eq/treble/level",
        "value_fn": lambda htp1: htp1.treble_level,
        "native_unit_of_measurement": "dB",       
        "device_class": "sound_pressure",         
        "state_class": "measurement",
        "icon": "mdi:knob",                           
    },
    {
        "key": "treble_frequency",
        "name": "Treble Corner Frequency",
        "path": "/eq/treble/freq",
        "value_fn": lambda htp1: htp1.treble_frequency,
        "native_unit_of_measurement": "Hz",        
        "device_class": "frequency",               
        "state_class": "measurement",              
        "icon": "mdi:sine-wave",                   
    },
    {
        "key": "tone_control",
        "name": "Tone Control",
        "path": "/eq/tc",
        "value_fn": lambda htp1: STATE_ON if htp1.tone_control else STATE_OFF,
        "icon": "mdi:music-note",       
    },
    {
        "key": "loudness_cal",
        "name": "Loudness Calibration",
        "path": "/loudnessCal",
        "value_fn": lambda htp1: htp1.loudness_cal,
        "native_unit_of_measurement": "dB",       
        "device_class": "sound_pressure",         
        "state_class": "measurement",             
        "icon": "mdi:knob",                   
    },

    {
        "key": "loudness_status",
        "name": "Loudness Status",
        "path": "/loudness",
        "value_fn": lambda htp1: htp1.loudness_raw,
        "icon": "mdi:ear-hearing",                   
    },
    {
        "key": "video_resolution",
        "name": "Video Resolution",
        "path": "/videostat/VideoResolution",
        "value_fn": lambda htp1: htp1.video_resolution,
        "icon": "mdi:television",                   
        "entity_category": "diagnostic",
    },
    {
        "key": "video_colorspace",
        "name": "Video Color Space",
        "path": "/videostat/VideoColorSpace",
        "value_fn": lambda htp1: htp1.video_colorspace,
        "icon": "mdi:television",                           
        "entity_category": "diagnostic",
    },
    {
        "key": "video_mode",
        "name": "Video Mode",
        "path": "/videostat/VideoMode",
        "value_fn": lambda htp1: htp1.video_mode,
        "icon": "mdi:television",                           
        "entity_category": "diagnostic",
    },
    {
        "key": "video_bitdepth",
        "name": "Video Bit Depth",
        "path": "/videostat/VideoBitDepth",
        "value_fn": lambda htp1: htp1.video_bitdepth,
        "icon": "mdi:television",                           
        "entity_category": "diagnostic",
    },
    {
        "key": "video_hdrstatus",
        "name": "Video HDR Status",
        "path": "/videostat/HDRstatus",
        "value_fn": lambda htp1: htp1.video_hdrstatus,
        "icon": "mdi:television",                           
        "entity_category": "diagnostic",
    },
    {
        "key": "sourceprogram",
        "name": "Audio Source Program",
        "path": "/status/DECSourceProgram",
        "value_fn": lambda htp1: htp1.sourceprogram,
        "icon": "mdi:speaker",                           
        "entity_category": "diagnostic",
    },
    {
        "key": "surroundmode",
        "name": "Audio Surround Mode",
        "path": "/status/SurroundMode",
        "value_fn": lambda htp1: htp1.surroundmode,
        "icon": "mdi:speaker",                           
        "entity_category": "diagnostic",
    },
    {
        "key": "decsamplerate",
        "name": "Audio Samplerate",
        "path": "/status/DECSampleRate",
        "value_fn": lambda htp1: htp1.decsamplerate,
        "icon": "mdi:speaker",                           
        "entity_category": "diagnostic",
    },
    {
        "key": "decprogramformat",
        "name": "Audio Program Format",
        "path": "/status/DECProgramFormat",
        "value_fn": lambda htp1: htp1.decprogramformat,
        "icon": "mdi:speaker",                           
        "entity_category": "diagnostic",
    },
    {
        "key": "channeltrim_left",
        "name": "Trim Left",
        "path": "/channeltrim/channels/lf",
        "value_fn": lambda htp1: htp1.channeltrim_left,
        "native_unit_of_measurement": "dB",       
        "suggested_display_precision": 2,
        "device_class": "sound_pressure",         
        "state_class": "measurement",
        "icon": "mdi:knob",                           
    },
    {
        "key": "channeltrim_right",
        "name": "Trim Right",
        "path": "/channeltrim/channels/rf",
        "value_fn": lambda htp1: htp1.channeltrim_right,
        "native_unit_of_measurement": "dB",
        "suggested_display_precision": 2,        
        "device_class": "sound_pressure",         
        "state_class": "measurement",
        "icon": "mdi:knob",                           
    },
    {
        "key": "channeltrim_center",
        "name": "Trim Center",
        "path": "/channeltrim/channels/c",
        "value_fn": lambda htp1: htp1.channeltrim_center,
        "native_unit_of_measurement": "dB",
        "suggested_display_precision": 2,        
        "device_class": "sound_pressure",         
        "state_class": "measurement",
        "icon": "mdi:knob",                           
    },
    {
        "key": "channeltrim_lfe",
        "name": "Trim LFE",
        "path": "/channeltrim/channels/lfe",
        "value_fn": lambda htp1: htp1.channeltrim_lfe,
        "native_unit_of_measurement": "dB",
        "suggested_display_precision": 2,        
        "device_class": "sound_pressure",         
        "state_class": "measurement",
        "icon": "mdi:knob",                           
    },
    {
        "key": "channeltrim_rightsurround",
        "name": "Trim Right Surround",
        "path": "/channeltrim/channels/rs",
        "value_fn": lambda htp1: htp1.channeltrim_rightsurround,
        "native_unit_of_measurement": "dB",
        "suggested_display_precision": 2,        
        "device_class": "sound_pressure",         
        "state_class": "measurement",
        "icon": "mdi:knob",                           
    },
    {
        "key": "channeltrim_leftsurround",
        "name": "Trim Left Surround",
        "path": "/channeltrim/channels/ls",
        "value_fn": lambda htp1: htp1.channeltrim_leftsurround,
        "native_unit_of_measurement": "dB",       
        "suggested_display_precision": 2,
        "device_class": "sound_pressure",         
        "state_class": "measurement",
        "icon": "mdi:knob",                           
    },
    {
        "key": "channeltrim_rightback",
        "name": "Trim Right Back",
        "path": "/channeltrim/channels/rb",
        "value_fn": lambda htp1: htp1.channeltrim_rightback,
        "native_unit_of_measurement": "dB",
        "suggested_display_precision": 2,        
        "device_class": "sound_pressure",         
        "state_class": "measurement",
        "icon": "mdi:knob",                           
    },
    {
        "key": "channeltrim_leftback",
        "name": "Trim Left Back",
        "path": "/channeltrim/channels/lb",
        "value_fn": lambda htp1: htp1.channeltrim_leftback,
        "native_unit_of_measurement": "dB",       
        "suggested_display_precision": 2,
        "device_class": "sound_pressure",         
        "state_class": "measurement",
        "icon": "mdi:knob",                           
    },
    {
        "key": "channeltrim_ltf",
        "name": "Trim Left Top Front",
        "path": "/channeltrim/channels/ltf",
        "value_fn": lambda htp1: htp1.channeltrim_ltf,
        "native_unit_of_measurement": "dB",
        "suggested_display_precision": 2,
        "device_class": "sound_pressure",
        "state_class": "measurement",
        "icon": "mdi:knob",
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_rtf",
        "name": "Trim Right Top Front",
        "path": "/channeltrim/channels/rtf",
        "value_fn": lambda htp1: htp1.channeltrim_rtf,
        "native_unit_of_measurement": "dB",
        "suggested_display_precision": 2,
        "device_class": "sound_pressure",
        "state_class": "measurement",
        "icon": "mdi:knob",
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_ltm",
        "name": "Trim Left Top Middle",
        "path": "/channeltrim/channels/ltm",
        "value_fn": lambda htp1: htp1.channeltrim_ltm,
        "native_unit_of_measurement": "dB",
        "suggested_display_precision": 2,
        "device_class": "sound_pressure",
        "state_class": "measurement",
        "icon": "mdi:knob",
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_rtm",
        "name": "Trim Right Top Middle",
        "path": "/channeltrim/channels/rtm",
        "value_fn": lambda htp1: htp1.channeltrim_rtm,
        "native_unit_of_measurement": "dB",
        "suggested_display_precision": 2,
        "device_class": "sound_pressure",
        "state_class": "measurement",
        "icon": "mdi:knob",
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_ltr",
        "name": "Trim Left Top Rear",
        "path": "/channeltrim/channels/ltr",
        "value_fn": lambda htp1: htp1.channeltrim_ltr,
        "native_unit_of_measurement": "dB",
        "suggested_display_precision": 2,
        "device_class": "sound_pressure",
        "state_class": "measurement",
        "icon": "mdi:knob",
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_rtr",
        "name": "Trim Right Top Rear",
        "path": "/channeltrim/channels/rtr",
        "value_fn": lambda htp1: htp1.channeltrim_rtr,
        "native_unit_of_measurement": "dB",
        "suggested_display_precision": 2,
        "device_class": "sound_pressure",
        "state_class": "measurement",
        "icon": "mdi:knob",
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_lw",
        "name": "Trim Left Wide",
        "path": "/channeltrim/channels/lw",
        "value_fn": lambda htp1: htp1.channeltrim_lw,
        "native_unit_of_measurement": "dB",
        "suggested_display_precision": 2,
        "device_class": "sound_pressure",
        "state_class": "measurement",
        "icon": "mdi:knob",
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_rw",
        "name": "Trim Right Wide",
        "path": "/channeltrim/channels/rw",
        "value_fn": lambda htp1: htp1.channeltrim_rw,
        "native_unit_of_measurement": "dB",
        "suggested_display_precision": 2,
        "device_class": "sound_pressure",
        "state_class": "measurement",
        "icon": "mdi:knob",
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_lfh",
        "name": "Trim Left Front Height",
        "path": "/channeltrim/channels/lfh",
        "value_fn": lambda htp1: htp1.channeltrim_lfh,
        "native_unit_of_measurement": "dB",
        "suggested_display_precision": 2,
        "device_class": "sound_pressure",
        "state_class": "measurement",
        "icon": "mdi:knob",
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_rfh",
        "name": "Trim Right Front Height",
        "path": "/channeltrim/channels/rfh",
        "value_fn": lambda htp1: htp1.channeltrim_rfh,
        "native_unit_of_measurement": "dB",
        "suggested_display_precision": 2,
        "device_class": "sound_pressure",
        "state_class": "measurement",
        "icon": "mdi:knob",
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_lhb",
        "name": "Trim Left Height Back",
        "path": "/channeltrim/channels/lhb",
        "value_fn": lambda htp1: htp1.channeltrim_lhb,
        "native_unit_of_measurement": "dB",
        "suggested_display_precision": 2,
        "device_class": "sound_pressure",
        "state_class": "measurement",
        "icon": "mdi:knob",
        "entity_registry_enabled_default": False,
    },
    {
        "key": "channeltrim_rhb",
        "name": "Trim Right Height Back",
        "path": "/channeltrim/channels/rhb",
        "value_fn": lambda htp1: htp1.channeltrim_rhb,
        "native_unit_of_measurement": "dB",
        "suggested_display_precision": 2,
        "device_class": "sound_pressure",
        "state_class": "measurement",
        "icon": "mdi:knob",
        "entity_registry_enabled_default": False,
    },
    {
        "key": "peq_status",
        "name": "PEQ Status",
        "path": "/peq/peqsw",
        "value_fn": lambda htp1: STATE_ON if htp1.peq_status else STATE_OFF,
        "icon": "mdi:music-note",       
    },

]


async def async_setup_entry(hass, entry, async_add_entities):
    htp1 = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        Htp1Sensor(
            htp1=htp1,
            entry_id=entry.entry_id,
            **definition,
        )
        for definition in SENSOR_DEFINITIONS
    ]

    async_add_entities(sensors)

class Htp1Sensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        htp1,                           # <-- Tama parametri on pakollinen
        entry_id: str,
        key: str,
        name: str,
        path: str,
        value_fn,
        icon=None,
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
        suggested_display_precision=None,
        entity_registry_enabled_default: bool = True,
        entity_category=None,
    ):
        """Initialize the sensor."""
        self._htp1 = htp1               # <-- TaMa RIVI PUUTTUU SINULTA!
        self._path = path
        self._value_fn = value_fn

        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_suggested_display_precision = suggested_display_precision

        self._attr_entity_registry_enabled_default = entity_registry_enabled_default
        # Entity category korjaus (toimiva versio)
        if isinstance(entity_category, str) and entity_category.lower() == "diagnostic":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif entity_category == "config":
            self._attr_entity_category = EntityCategory.CONFIG
        else:
            self._attr_entity_category = entity_category  # None tai jo enum

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Monoprice",
            model="HTP-1",
            name="HTP-1",
        )

    @property
    def native_value(self):
        try:
            return self._value_fn(self._htp1)
        except Exception:
            return None

    async def async_added_to_hass(self):
        self._htp1.subscribe(self._path, self._handle_update)

    async def _handle_update(self, value):
        self.async_write_ha_state()

