"""Peak level and clipping from the HTP-1 interval meter feed.

avController serves the output meters as Server-Sent Events on port 8081
(`/vui/events`): one `vui` frame per 50 ms with 25 meter bytes while the audio
pipeline runs, `vui-status` once a second when there is nothing to report.
Each byte: bit 7 = channel active, bit 6 = clipped during the interval,
bits 0-5 = level index into VU_DBFS. The frames are folded into a window of
WINDOW_S seconds and the result is published to subscribers of "#peak".

The feed is read only while at least one peak entity is enabled and the unit
is on, so the unit does not poll its meters for nobody.
"""

from __future__ import annotations

import asyncio
import logging
import time
from json import loads
from typing import TYPE_CHECKING, Any

import aiohttp

if TYPE_CHECKING:
    from .aiohtp1 import Htp1

_LOGGER = logging.getLogger(__name__)

PEAK_SUBJECT = "#peak"
FEED_PORT = 8081
WINDOW_S = 2.0          # one published value per window at most
CLIP_HOLD_S = 10.0      # the clipping flag stays on this long after a clip
RETRY_MIN_S = 5.0
RETRY_MAX_S = 300.0
OLD_FIRMWARE_RETRY_S = 300.0

# Level index -> dBFS (htp1-custom-controller src/calibration/vuDecode.js).
# Index 0 is below the meter floor (-84 dBFS), 54 = 0 dBFS, 63 = +6 dBFS.
VU_DBFS: list[float | None] = [
    None,
    -80, -76, -72, -68, -64, -60,
    -58, -56, -54, -52, -50, -48, -46, -44, -42, -40,
    -38, -36, -34, -32, -30, -28, -26, -24, -22, -20,
    -19, -18, -17, -16, -15, -14, -13, -12, -11, -10,
    -9, -8, -7, -6,
    -5.5, -5, -4.5, -4, -3.5, -3, -2.5, -2, -1.5, -1,
    -0.75, -0.5, -0.25,
    0, 0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4.5, 6,
]
assert len(VU_DBFS) == 64

# Order of the 25 meter values (useSpeakerGroups.js allChannelCodes + Mix Out).
VU_CHANNELS = [
    "lf", "rf", "c", "sub1", "sub2", "sub3", "ls", "rs", "lb", "rb",
    "ltf", "rtf", "ltm", "rtm", "ltr", "rtr", "lw", "rw",
    "lfh", "rfh", "lhb", "rhb", "sub4", "sub5", "mixout",
]
VU_LABELS = [
    "Left Front", "Right Front", "Center", "Subwoofer 1", "Subwoofer 2", "Subwoofer 3",
    "Left Surround", "Right Surround", "Left Back", "Right Back",
    "Left Top Front", "Right Top Front", "Left Top Middle", "Right Top Middle",
    "Left Top Rear", "Right Top Rear", "Left Wide", "Right Wide",
    "Left Front Height", "Right Front Height", "Left Rear Height", "Right Rear Height",
    "Subwoofer 4", "Subwoofer 5", "Mix Out",
]
MIX_OUT_INDEX = 24
SUB_INDEX = {"sub1": 3, "sub2": 4, "sub3": 5, "sub4": 22, "sub5": 23}

# Speaker group (/speakers/groups/<group>) of each channel; "lr" has no present flag.
CHANNEL_GROUP = {
    "lf": "lr", "rf": "lr", "c": "c", "ls": "lrs", "rs": "lrs", "lb": "lrb", "rb": "lrb",
    "ltf": "lrtf", "rtf": "lrtf", "ltm": "lrtm", "rtm": "lrtm", "ltr": "lrtr", "rtr": "lrtr",
    "lw": "lrw", "rw": "lrw", "lfh": "lrhf", "rfh": "lrhf", "lhb": "lrhr", "rhb": "lrhr",
    "sub1": "sub1", "sub2": "sub2", "sub3": "sub3", "sub4": "sub4", "sub5": "sub5",
}


def accept_frame(frame: Any, last_seq: int | None) -> bool:
    """The front panel's rules (status.html acceptPeakInterval)."""
    if not isinstance(frame, dict):
        return False
    seq = frame.get("seq")
    if isinstance(seq, bool) or not isinstance(seq, int) or not 0 <= seq <= 127 or seq == last_seq:
        return False
    channels = frame.get("channels")
    if not isinstance(channels, list) or len(channels) != len(VU_CHANNELS):
        return False
    return all(
        isinstance(raw, int) and not isinstance(raw, bool) and 128 <= raw <= 255 for raw in channels
    )


class PeakMonitor:
    """Reads the meter feed of one unit while someone needs it."""

    def __init__(self, htp1: Htp1) -> None:
        self._htp1 = htp1
        self._users = 0
        self._task: asyncio.Task | None = None
        self._wake = asyncio.Event()
        self._published: Any = None
        self._last_clip: tuple[float, float | None, list[str]] | None = None
        htp1.subscribe("/powerIsOn", self._on_state)
        htp1.subscribe("#connection", self._on_state)

    # ------------------------------------------------------------------ lifecycle

    @property
    def value(self) -> dict[str, Any] | None:
        """Last published window, or None while there is no feed."""
        return self._published

    def acquire(self) -> None:
        self._users += 1
        self._update()

    def release(self) -> None:
        self._users = max(0, self._users - 1)
        self._update()

    def _on_state(self, _value=None) -> None:
        if self._htp1.connected:
            self._wake.set()        # a reconnect retries a waiting reader at once
        self._update()

    def _wanted(self) -> bool:
        return self._users > 0 and self._htp1.connected and self._htp1.power is True

    def _update(self) -> None:
        if self._wanted():
            if self._task is None or self._task.done():
                self._task = asyncio.get_running_loop().create_task(self._run())
        elif self._task is not None:
            self._task.cancel()
            self._task = None
            self._schedule_publish(None)

    async def stop(self) -> None:
        self._users = 0
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._published = None

    # ------------------------------------------------------------------ publishing

    def _schedule_publish(self, value: dict[str, Any] | None) -> None:
        if value != self._published:
            self._published = value
            asyncio.get_running_loop().create_task(self._htp1._notify(PEAK_SUBJECT, value))

    async def _publish(self, value: dict[str, Any] | None) -> None:
        if value != self._published:
            self._published = value
            await self._htp1._notify(PEAK_SUBJECT, value)

    def _channel_labels(self) -> list[str | None]:
        """Label per meter index for the channels in use; None for unused outputs."""
        state = self._htp1._state or {}
        groups = (state.get("speakers") or {}).get("groups") or {}
        labels: list[str | None] = []
        for index, code in enumerate(VU_CHANNELS[:MIX_OUT_INDEX]):
            group = CHANNEL_GROUP[code]
            present = group == "lr" or bool((groups.get(group) or {}).get("present"))
            labels.append(VU_LABELS[index] if present else None)
        labels.append(VU_LABELS[MIX_OUT_INDEX])

        # Seat Shaker (status.html getSeatShakerVuIndex)
        shaker = state.get("shaker") or {}
        output = shaker.get("output")
        if output in ("mono17", "diff17"):
            labels[MIX_OUT_INDEX] = "Seat Shaker"
        elif output == "nextsub" and shaker.get("enabled"):
            last = max((i for i in range(1, 6) if (groups.get(f"sub{i}") or {}).get("present")), default=0)
            index = SUB_INDEX.get(f"sub{last + 1}")
            if index is not None:
                labels[index] = "Seat Shaker"
        return labels

    def _window_value(self, levels: list[int], clips: int, now: float) -> dict[str, Any]:
        labels = self._channel_labels()
        top = -1
        top_index = None
        for index, label in enumerate(labels):
            if label is not None and levels[index] > top:
                top = levels[index]
                top_index = index
        clip_labels = [labels[i] for i in range(len(labels)) if labels[i] and clips & (1 << i)]
        if clip_labels:
            clip_level = max(
                (VU_DBFS[levels[i]] for i in range(len(labels))
                 if labels[i] and clips & (1 << i) and VU_DBFS[levels[i]] is not None),
                default=None,
            )
            self._last_clip = (now, clip_level, clip_labels)
        level = VU_DBFS[top] if top_index is not None and top > 0 else None
        clipping = self._last_clip is not None and now - self._last_clip[0] < CLIP_HOLD_S
        return {
            "level": level,
            "channel": labels[top_index] if level is not None else None,
            "clipping": clipping,
            "clip_channels": list(self._last_clip[2]) if clipping else [],
            "clip_level": self._last_clip[1] if clipping else None,
        }

    # ------------------------------------------------------------------ reader

    async def _run(self) -> None:
        delay = RETRY_MIN_S
        while self._wanted():
            wait = delay
            try:
                old_firmware = await self._read_feed()
                delay = RETRY_MIN_S
                wait = OLD_FIRMWARE_RETRY_S if old_firmware else RETRY_MIN_S
            except asyncio.CancelledError:
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError) as err:
                _LOGGER.debug("HTP-1 meter feed: %s", err)
                delay = min(delay * 2, RETRY_MAX_S)
            await self._publish(None)
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), wait)
            except asyncio.TimeoutError:
                pass

    async def _read_feed(self) -> bool:
        """Read until the stream ends. Returns True when the firmware has no interval feed."""
        url = f"http://{self._htp1.host}:{FEED_PORT}/vui/events"
        timeout = aiohttp.ClientTimeout(total=None, connect=10, sock_read=10)
        async with self._htp1.session.get(url, timeout=timeout) as resp:
            if resp.status != 200:
                _LOGGER.debug("HTP-1 meter feed: HTTP %s", resp.status)
                return True
            last_seq: int | None = None
            levels = [0] * len(VU_CHANNELS)
            clips = 0
            window_end = time.monotonic() + WINDOW_S
            event = ""
            data = ""
            async for raw_line in resp.content:
                line = raw_line.decode("utf-8", "replace").rstrip("\r\n")
                if line.startswith("event:"):
                    event = line[6:].strip()
                    continue
                if line.startswith("data:"):
                    data = line[5:].strip()
                    continue
                if line:
                    continue                     # comments and fields this reader does not use
                # a blank line ends the event
                name, payload, event, data = event, data, "", ""
                if name == "vui":
                    try:
                        frame = loads(payload)
                    except ValueError:
                        continue
                    if not accept_frame(frame, last_seq):
                        continue
                    last_seq = frame["seq"]
                    for index, raw in enumerate(frame["channels"]):
                        level = raw & 0x3F
                        if level > levels[index]:
                            levels[index] = level
                        if raw & 0x40:
                            clips |= 1 << index
                    now = time.monotonic()
                    if now >= window_end:
                        await self._publish(self._window_value(levels, clips, now))
                        levels = [0] * len(VU_CHANNELS)
                        clips = 0
                        window_end = now + WINDOW_S
                elif name == "vui-status":
                    if payload.strip('"') == "unsupported":
                        _LOGGER.debug("HTP-1 meter feed: APM firmware too old")
                        return True
                    last_seq = None
                    levels = [0] * len(VU_CHANNELS)
                    clips = 0
                    await self._publish(None)    # unit off or pipeline stopped
                elif name in ("vu", "vupeak"):
                    _LOGGER.debug("HTP-1 meter feed: old controller without the interval feed")
                    return True
        return False
