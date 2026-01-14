"""The aiohttp Monoprice HTP-1 client library."""

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from json import dumps, loads
from logging import getLogger
from typing import Any
from .trigger_manager import TriggerManager

import aiodns
import aiohttp


class AioHtp1Exception(Exception):
    pass


class ConnectionException(AioHtp1Exception):
    pass


class Htp1:
    RECONNECT_DELAY_INITIAL = 3
    RECONNECT_DELAY_MAX = 60
    MSO_WAIT_TIMEOUT = 5

    log = getLogger("aiohtp1")

    def __init__(self, host: str, session: aiohttp.ClientSession) -> None:
        self.host = host
        self.session = session

        self._websocket: aiohttp.ClientWebSocketResponse | None = None
        self._receive_task: Awaitable[None] | None = None
        self._try_connect_task: Awaitable[None] | None = None
       
        self._subscriptions: dict[str, list[Callable]] = {}
        self._state: dict[str, Any] | None = None
        self._state_ready = asyncio.Event()
        self._tx: dict[str, Any] | None = None

        self._trying_to_connect = False
        self._ha_stopping = False

        self.trigger = TriggerManager(self)

        self.reset()

    def reset(self):
        self._state = None
        self._tx = None
        self._state_ready.clear()

    @property
    def connected(self):
        return self._state_ready.is_set()

    #
    # CONNECT
    #

    async def connect(self):
        self.reset()
        url = f"ws://{self.host}/ws/controller"
        self.log.debug("connect: %s", url)

        try:
            self._websocket = await self.session.ws_connect(url)

        except asyncio.CancelledError:
            self.log.debug("connect cancelled: HA shutdown")
            raise

        except (TimeoutError, aiodns.error.DNSError, aiohttp.ClientError) as err:
            await self._disconnect()
            raise ConnectionException from err

        # start receive loop
        self._receive_task = asyncio.create_task(self._receive())

        # request initial state
        await self._websocket.send_str("getmso")
        async with asyncio.timeout(self.MSO_WAIT_TIMEOUT):
            await self._state_ready.wait()

        await self._notify("#connection")

    #
    # DISCONNECT
    #

    async def _disconnect(self):
        if self._websocket is not None:
            with suppress(Exception):
                await self._websocket.close()

        if self._receive_task is not None:
            self._receive_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._receive_task
            self._receive_task = None

        self._websocket = None

    #
    # RECONNECT MANAGER
    #

    async def try_connect(self):
        if self._try_connect_task:
            return  # already running
        self._try_connect_task = asyncio.create_task(self._try_connect_loop())

    async def _try_connect_loop(self):
        self._trying_to_connect = True
        delay = self.RECONNECT_DELAY_INITIAL

        try:
            while self._trying_to_connect:
                try:
                    await self.connect()
                    return
                except ConnectionException:
                    pass

                # interruptible sleep
                remaining = delay
                while remaining > 0 and self._trying_to_connect:
                    await asyncio.sleep(1)
                    remaining -= 1

                delay = min(delay * 2, self.RECONNECT_DELAY_MAX)

        except asyncio.CancelledError:
            raise
        finally:
            self._trying_to_connect = False
            self._try_connect_task = None

    async def _stop_connect(self):
        self._trying_to_connect = False
        if self._try_connect_task:
            self._try_connect_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._try_connect_task
            self._try_connect_task = None

    #
    # RECEIVE LOOP
    #

    async def _receive(self):
        try:
            while True:
                try:
                    msg = await self._websocket.receive()
                except asyncio.CancelledError:
                    raise
                except Exception as err:
                    self.log.warning("socket error: %s", err)
                    break

                if msg.type in (
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.ERROR,
                ):
                    break

                if msg.type != aiohttp.WSMsgType.TEXT:
                    continue

                data = msg.data
                if " " not in data:
                    continue

                cmd, payload = data.split(" ", 1)
                handler = getattr(self, f"_cmd_{cmd}", None)
                if not handler:
                    continue

                try:
                    await handler(loads(payload))
                except Exception:
                    self.log.exception("handler failed")

        finally:
            self._state_ready.clear()

            # schedule reconnect unless HA shutting down
            if not self._ha_stopping:
                asyncio.create_task(self.try_connect())

            await self._notify("#connection")

    #
    # STOP
    #

    async def stop(self):
        self._ha_stopping = True
        await self._stop_connect()
        await self._disconnect()
        self.reset()

    #
    # COMMAND HANDLERS
    #

    async def _cmd_mso(self, payload):
        self._state = payload
        self._state_ready.set()


    async def _cmd_msoupdate(self, payload):
        if not isinstance(payload, list):
            payload = [payload]

        for piece in payload:
            op = piece["op"]
            path = piece["path"][1:].split("/")
            target = self._state
            final = path.pop()

            if op not in ("add", "replace"):
                continue

            for node in path:
                if isinstance(target, list):
                    node = int(node)
                target = target[node]

            value = piece["value"]
            target[final] = value

            await self._notify(piece["path"], value)



    #
    # SUBSCRIPTIONS
    #

    def subscribe(self, subject, callback):
        self._subscriptions.setdefault(subject, []).append(callback)

    async def _notify(self, subject, value=None):
        for cb in self._subscriptions.get(subject, []):
            await cb(value)

    #
    # TRANSACTION SYSTEM
    #

    async def __aenter__(self):
        if self._tx is not None:
            raise AioHtp1Exception("tx already active")
        self._tx = {}
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._tx = None


    async def commit(self):
        if not self._tx:
            return False

        ops = [{"op": "replace", "path": k, "value": v} for k, v in self._tx.items()]
        payload = dumps(ops, separators=(",", ":"))
        await self._websocket.send_str(f"changemso {payload}")

        self._tx = {}
        return True


    async def send_avcui(self, command: str):
        if not self._websocket:
            raise AioHtp1Exception("Not connected")

        await self._websocket.send_str(f'avcui "{command}"')





    #
    # ALL YOUR PROPERTY ACCESSORS (unchanged)
    #


    ## Operations


    @property
    def serial_number(self):
        """Retrieve the HTP-1 device's serial number."""
        return self._state["versions"]["SerialNumber"]

    @property
    def cal_vph(self):
        """Retrieve the HTP-1 device's calibration max volume."""
        return self._state["cal"]["vph"]

    @property
    def cal_vpl(self):
        """Retrieve the HTP-1 device's calibration min volume."""
        return self._state["cal"]["vpl"]

    @property
    def cal_current_dirac_slot(self):
        """Active Dirac slot index (0-2)."""
        if not self._state:
            return None
        try:
            return int(self._state["cal"]["currentdiracslot"])
        except Exception:
            return None

    @cal_current_dirac_slot.setter
    def cal_current_dirac_slot(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        v = int(value)
        if v < 0 or v > 2:
            raise AioHtp1Exception("slot out of range (0-2)")
        self._tx["/cal/currentdiracslot"] = v


    @property
    def loudness_raw(self):
        if not self._state:
            return "off"
        return self._state.get("loudness", "off")

    @property
    def muted(self):
        try:
            return self._tx["/muted"]
        except Exception:
            pass
        return self._state.get("muted") if self._state else False


    @muted.setter
    def muted(self, value):
        """Set the HTP-1 device's muted value."""
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/muted"] = value

    @property
    def volume(self):
        try:
            return self._tx["/volume"]
        except Exception:
            pass
        return self._state.get("volume") if self._state else None


    @volume.setter
    def volume(self, value):
        """Set the HTP-1 device's volume."""
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/volume"] = value

    @property
    def power(self):
        try:
            return self._tx["/powerIsOn"]
        except Exception:
            pass
        if self._state and "powerIsOn" in self._state:
            return self._state["powerIsOn"]
        return None

    @power.setter
    def power(self, value):
        """Set the HTP-1 device's power state."""
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/powerIsOn"] = value


    @property
    def input(self):
        if not self._state:
            return None

        try:
            _id = self._tx.get("/input") if self._tx else None
        except Exception:
            _id = None

        if _id is None:
            _id = self._state.get("input")

        try:
            return self._state["inputs"][_id]["label"]
        except Exception:
            return None


    @input.setter
    def input(self, value):
        """Set the HTP-1 device's input."""
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        for _id, info in self._state["inputs"].items():
            if value == info["label"]:
                self._tx["/input"] = _id
                return
        raise AioHtp1Exception("input '{value}' not found")


    @property
    def inputs(self):
        if not self._state:
            return []
        try:
            return [i["label"] for i in self._state["inputs"].values() if i.get("visible")]
        except Exception:
            return []

    @property
    def upmix(self):
        if not self._state:
            return None
        try:
            return self._tx.get("/upmix/select")
        except Exception:
            pass
        try:
            return self._state["upmix"]["select"]
        except Exception:
            return None


    @upmix.setter
    def upmix(self, value):
        """Set the HTP-1 device's upmix."""
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/upmix/select"] = value

    @property
    def upmixes(self):
        if not self._state:
            return []
        try:
            return [
                k for k, v in self._state["upmix"].items()
                if k != "select" and v.get("homevis")
            ]
        except Exception:
            return []

    @property
    def bass_level(self):
        if not self._state:
            return None
        try:
            return self._state["eq"]["bass"]["level"]
        except Exception:
            return None

    @bass_level.setter
    def bass_level(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/eq/bass/level"] = value

    @property
    def bass_frequency(self):
        if not self._state:
            return None
        try:
            return self._state["eq"]["bass"]["freq"]
        except Exception:
            return None

    @bass_frequency.setter
    def bass_frequency(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/eq/bass/freq"] = value

    @property
    def treble_level(self):
        if not self._state:
            return None
        try:
            return self._state["eq"]["treble"]["level"]
        except Exception:
            return None

    @treble_level.setter
    def treble_level(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/eq/treble/level"] = value

    @property
    def treble_frequency(self):
        if not self._state:
            return None
        try:
            return self._state["eq"]["treble"]["freq"]
        except Exception:
            return None

    @treble_frequency.setter
    def treble_frequency(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/eq/treble/freq"] = value

    @property
    def tone_control(self):
        if not self._state:
            return False
        try:
            return self._state["eq"]["tc"]
        except Exception:
            return False

    @tone_control.setter
    def tone_control(self, value: bool):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/eq/tc"] = value
        
    @property
    def loudness_cal(self):
        if not self._state:
            return None
        return self._state.get("loudnessCal")

    @loudness_cal.setter
    def loudness_cal(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/loudnessCal"] = value

    @property
    def loudness_status(self):
        if not self._state:
            return False
        return self._state.get("loudness") == "on"


    @loudness_status.setter
    def loudness_status(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")

        self._tx["/loudness"] = "on" if value else "off"


    @property
    def lipsync_delay(self):
        if not self._state:
            return None
        try:
            return self._state["cal"]["lipsync"]
        except Exception:
            return None

    @lipsync_delay.setter
    def lipsync_delay(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/cal/lipsync"] = value


    @property
    def video_resolution(self):
        try:
            return self._state["videostat"]["VideoResolution"]
        except Exception:
            return None

    @property
    def video_colorspace(self):
        try:
            return self._state["videostat"]["VideoColorSpace"]
        except Exception:
            return None

    @property
    def video_mode(self):
        try:
            return self._state["videostat"]["VideoMode"]
        except Exception:
            return None

    @property
    def video_bitdepth(self):
        try:
            return self._state["videostat"]["VideoBitDepth"]
        except Exception:
            return None

    @property
    def video_hdrstatus(self):
        try:
            return self._state["videostat"]["HDRstatus"]
        except Exception:
            return None

    @property
    def peq_status(self):
        try:
            return self._state["peq"]["peqsw"]
        except Exception:
            return None


    @property
    def channeltrim_left(self):
        try:
            return self._state["channeltrim"]["channels"]["lf"]
        except Exception:
            return None

    @channeltrim_left.setter
    def channeltrim_left(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/channeltrim/channels/lf"] = value


    @property
    def channeltrim_right(self):
        try:
            return self._state["channeltrim"]["channels"]["rf"]
        except Exception:
            return None

    @channeltrim_right.setter
    def channeltrim_right(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/channeltrim/channels/rf"] = value


    @property
    def channeltrim_center(self):
        try:
            return self._state["channeltrim"]["channels"]["c"]
        except Exception:
            return None

    @channeltrim_center.setter
    def channeltrim_center(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/channeltrim/channels/c"] = value


    @property
    def channeltrim_lfe(self):
        try:
            return self._state["channeltrim"]["channels"]["lfe"]
        except Exception:
            return None

    @channeltrim_lfe.setter
    def channeltrim_lfe(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/channeltrim/channels/lfe"] = value


    @property
    def channeltrim_rightsurround(self):
        try:
            return self._state["channeltrim"]["channels"]["rs"]
        except Exception:
            return None

    @channeltrim_rightsurround.setter
    def channeltrim_rightsurround(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/channeltrim/channels/rs"] = value


    @property
    def channeltrim_leftsurround(self):
        try:
            return self._state["channeltrim"]["channels"]["ls"]
        except Exception:
            return None

    @channeltrim_leftsurround.setter
    def channeltrim_leftsurround(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/channeltrim/channels/ls"] = value


    @property
    def channeltrim_rightback(self):
        try:
            return self._state["channeltrim"]["channels"]["rb"]
        except Exception:
            return None

    @channeltrim_rightback.setter
    def channeltrim_rightback(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/channeltrim/channels/rb"] = value


    @property
    def channeltrim_leftback(self):
        try:
            return self._state["channeltrim"]["channels"]["lb"]
        except Exception:
            return None

    @channeltrim_leftback.setter
    def channeltrim_leftback(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/channeltrim/channels/lb"] = value



    @property
    def secondvolume(self):
        try:
            return self._state["secondVolume"]
        except Exception:
            return None


    @secondvolume.setter
    def secondvolume(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/secondVolume"] = value


    @property
    def sourceprogram(self):
        try:
            return self._state["status"]["DECSourceProgram"]
        except Exception:
            return None

    @property
    def surroundmode(self):
        try:
            return self._state["status"]["SurroundMode"]
        except Exception:
            return None

    @property
    def decsamplerate(self):
        try:
            return self._state["status"]["DECSampleRate"]
        except Exception:
            return None

    @property
    def decprogramformat(self):
        try:
            return self._state["status"]["DECProgramFormat"]
        except Exception:
            return None


    @property
    def channeltrim_ltf(self):
        try:
            return self._state["channeltrim"]["channels"]["ltf"]
        except Exception:
            return None

    @channeltrim_ltf.setter
    def channeltrim_ltf(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/channeltrim/channels/ltf"] = value


    @property
    def channeltrim_rtf(self):
        try:
            return self._state["channeltrim"]["channels"]["rtf"]
        except Exception:
            return None

    @channeltrim_rtf.setter
    def channeltrim_rtf(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/channeltrim/channels/rtf"] = value


    @property
    def channeltrim_ltm(self):
        try:
            return self._state["channeltrim"]["channels"]["ltm"]
        except Exception:
            return None

    @channeltrim_ltm.setter
    def channeltrim_ltm(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/channeltrim/channels/ltm"] = value


    @property
    def channeltrim_rtm(self):
        try:
            return self._state["channeltrim"]["channels"]["rtm"]
        except Exception:
            return None

    @channeltrim_rtm.setter
    def channeltrim_rtm(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/channeltrim/channels/rtm"] = value


    @property
    def channeltrim_ltr(self):
        try:
            return self._state["channeltrim"]["channels"]["ltr"]
        except Exception:
            return None

    @channeltrim_ltr.setter
    def channeltrim_ltr(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/channeltrim/channels/ltr"] = value


    @property
    def channeltrim_rtr(self):
        try:
            return self._state["channeltrim"]["channels"]["rtr"]
        except Exception:
            return None

    @channeltrim_rtr.setter
    def channeltrim_rtr(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/channeltrim/channels/rtr"] = value


    @property
    def channeltrim_lw(self):
        try:
            return self._state["channeltrim"]["channels"]["lw"]
        except Exception:
            return None

    @channeltrim_lw.setter
    def channeltrim_lw(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/channeltrim/channels/lw"] = value


    @property
    def channeltrim_rw(self):
        try:
            return self._state["channeltrim"]["channels"]["rw"]
        except Exception:
            return None

    @channeltrim_rw.setter
    def channeltrim_rw(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/channeltrim/channels/rw"] = value


    @property
    def channeltrim_lfh(self):
        try:
            return self._state["channeltrim"]["channels"]["lfh"]
        except Exception:
            return None

    @channeltrim_lfh.setter
    def channeltrim_lfh(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/channeltrim/channels/lfh"] = value


    @property
    def channeltrim_rfh(self):
        try:
            return self._state["channeltrim"]["channels"]["rfh"]
        except Exception:
            return None

    @channeltrim_rfh.setter
    def channeltrim_rfh(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/channeltrim/channels/rfh"] = value


    @property
    def channeltrim_lhb(self):
        try:
            return self._state["channeltrim"]["channels"]["lhb"]
        except Exception:
            return None

    @channeltrim_lhb.setter
    def channeltrim_lhb(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/channeltrim/channels/lhb"] = value


    @property
    def channeltrim_rhb(self):
        try:
            return self._state["channeltrim"]["channels"]["rhb"]
        except Exception:
            return None

    @channeltrim_rhb.setter
    def channeltrim_rhb(self, value):
        if self._tx is None:
            raise AioHtp1Exception("no transaction in progress")
        self._tx["/channeltrim/channels/rhb"] = value
