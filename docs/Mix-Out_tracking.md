# Mix Out Volume Tracking — New Entities

## Switches

### Mix Out Volume Tracking (`switch.htp_1_mix_out_volume_tracking`)
Enables automatic tracking of the main volume by the Mix Out (secondary) output. When on, every main volume change triggers a recalculated Mix Out volume write to the device. Off by default. State persists across HA restarts.

When tracking is enabled, the Mix Out Power On Volume is also automatically updated to match the value that the tracking curve and offset would produce for the current main Power On Volume. This keeps the Mix Out startup level consistent with the tracking settings. The same update happens whenever a tracking parameter is changed.

### Mix Out Tracking Non-Linear Curve (`switch.htp_1_mix_out_tracking_non_linear_curve`)
Enables the non-linear shaping curve on top of tracking. When off, Mix Out simply follows main volume plus the offset (linear). When on, the curve parameters below take effect. Off by default.

---

## Numbers

### Mix Out Tracking Offset (`number.htp_1_mix_out_tracking_offset`)
Range: −30…+30 dB · Step: 1 dB · Default: 0 dB

A fixed offset added to the (shaped) main volume to produce the final Mix Out target. Applied regardless of whether the curve is enabled.

### Mix Out Tracking Threshold (`number.htp_1_mix_out_tracking_threshold`)
Range: −60…0 dB · Step: 1 dB · Default: −20 dB

The volume level below which the non-linear curve begins to apply a boost. Above this level, Mix Out follows main 1:1 (plus offset).

### Mix Out Tracking Boost (`number.htp_1_mix_out_tracking_boost`)
Range: 0…30 dB · Step: 1 dB · Default: 12 dB

The maximum boost applied at the Volume Floor. At the threshold the boost is zero; it grows towards this value as volume decreases.

### Mix Out Tracking Curve Exponent (`number.htp_1_mix_out_tracking_curve_exponent`)
Range: 0.1…5.0 · Step: 0.1 · Default: 1.0

Controls the shape of the boost curve between the threshold and the floor. `1.0` = linear growth. Values above 1 make the boost grow more slowly near the threshold and more steeply near the floor. Values below 1 do the opposite.

### Mix Out Tracking Volume Floor (`number.htp_1_mix_out_tracking_volume_floor`)
Range: −80…−20 dB · Step: 1 dB · Default: −60 dB

The volume level at which the full Boost is reached. Below this level the curve is clamped.

### Mix Out Tracking Delay (`number.htp_1_mix_out_tracking_delay`)
Range: 0.1…2.0 s · Step: 0.1 s · Default: 0.5 s

Debounce delay applied to volume tracking writes. When the main volume changes, the Mix Out write is deferred until the volume has been stable for this duration. This prevents flooding the device with messages during fast volume sweeps. Parameter changes (offset, curve settings) always write immediately regardless of this setting.

---

All six number entities and both switches persist their values across HA restarts via `RestoreEntity`. None of these settings map to a device WebSocket path — they are local to the integration.
