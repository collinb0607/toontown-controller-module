"""TTR's Local API (companion app support): the toon's laff, read from the game itself.

Each running TTR serves JSON on localhost, from port 1547 (one more port per extra
game, up to 1552). It needs Companion App Support on in TTR's Options, and TTR asks
in game, once per Authorization value, whether to allow the app: so one value is
made, saved and reused. Once allowed, a request takes a few milliseconds and laff
shows the change the moment it happens (tested in game, Nov 11).

`ToonWatcher` polls laff (and the toon, location and Unites) on a thread for the TTR process the controller plays (found
by which process owns the port) and hands the main loop each change; `rumble_for`
turns a change into a rumble.
"""

import ctypes
import http.client
import json
import secrets
import threading
import time
from collections import deque
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

PORTS = range(1547, 1553)
TOKEN_FILE = "ttr_api_token"  # beside config.json
AGENT = "Toontown Controller Module"
POLL_SECONDS = 0.1
RESCAN_SECONDS = 3.0
FIRST_TIMEOUT = 60.0  # the first request of a session waits while TTR asks the player
TIMEOUT = 1.0


def load_token(path: Path) -> str:
    """The saved Authorization value, made the first time (TTR asks once per value)."""
    try:
        token = path.read_text(encoding="utf-8").strip()
        if token:
            return token
    except OSError:
        pass
    token = secrets.token_hex(16)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(token, encoding="utf-8")
    except OSError:
        pass  # still works this session; TTR just asks again next time
    return token


def clear_token(path: Path) -> bool:
    """Forget the saved Authorization value (the settings window's reset). The next request
    makes a new one, and TTR asks the player again. True when there was one to delete."""
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


class ApiError(Exception):
    pass


def get_json(port: int, path: str, token: str, timeout: float = TIMEOUT):
    # 127.0.0.1, not "localhost": resolving localhost can try a dead address first.
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        connection.request("GET", path, headers={
            "Host": f"localhost:{port}", "User-Agent": AGENT, "Authorization": token})
        response = connection.getresponse()
        body = response.read()
        if response.status != 200:
            raise ApiError(f"HTTP {response.status} {response.reason}")
        return json.loads(body.decode("utf-8"))
    finally:
        connection.close()


# ---- which process listens on which port --------------------------------------------------
class _TcpRow(ctypes.Structure):
    _fields_ = [("state", wintypes.DWORD), ("local_addr", wintypes.DWORD), ("local_port", wintypes.DWORD),
                ("remote_addr", wintypes.DWORD), ("remote_port", wintypes.DWORD), ("pid", wintypes.DWORD)]


_AF_INET = 2
_TCP_TABLE_OWNER_PID_LISTENER = 3


def listening_ports() -> dict[int, int]:
    """API ports (1547-1552) being listened on, each with the process listening."""
    try:
        iphlpapi = ctypes.windll.iphlpapi
    except (AttributeError, OSError):
        return {}
    size = wintypes.DWORD(0)
    iphlpapi.GetExtendedTcpTable(None, ctypes.byref(size), False, _AF_INET, _TCP_TABLE_OWNER_PID_LISTENER, 0)
    buffer = ctypes.create_string_buffer(size.value + 1024)
    size = wintypes.DWORD(len(buffer))
    if iphlpapi.GetExtendedTcpTable(buffer, ctypes.byref(size), False, _AF_INET,
                                    _TCP_TABLE_OWNER_PID_LISTENER, 0) != 0:
        return {}
    count = wintypes.DWORD.from_buffer(buffer).value
    rows = (_TcpRow * count).from_buffer(buffer, ctypes.sizeof(wintypes.DWORD))
    found = {}
    for row in rows:
        port = ((row.local_port & 0xFF) << 8) | ((row.local_port >> 8) & 0xFF)  # network byte order
        if port in PORTS:
            found[port] = row.pid
    return found


# ---- laff changes ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LaffChange:
    old: int
    new: int
    max: int


HEAL = (0.0, 0.4, 120)  # laff went up: short and light, unlike a hit
FULL_HIT = 20  # this much damage or more: the strongest, longest rumble (the user, Nov 11)


def rumble_for(change: LaffChange) -> tuple[float, float, int] | None:
    """(heavy motor, light motor, milliseconds) for a hit, or None. It grows with the
    damage: 1 laff is a tiny short tap, FULL_HIT or more is full strength and long.
    Going sad rumbles full and longest. Laff going up is a short light buzz (the light
    motor only), a notice rather than a hit."""
    if change.new == change.old:
        return None
    if change.new > change.old:
        return HEAL
    if change.new <= 0:
        return 1.0, 1.0, 900
    part = min(change.old - change.new, FULL_HIT) / FULL_HIT
    power = 0.15 + 0.85 * part
    return power, power * 0.6, round(80 + 420 * part)


@dataclass(frozen=True)
class ToonInfo:
    """What the main loop uses about the toon in the followed game (None: not known,
    such as with Companion App Support off, or not logged in to a toon)."""
    id: str | None = None
    name: str | None = None
    zone: str | None = None
    neighborhood: str | None = None
    unites: int | None = None  # how many Unites it has, all kinds together
    district: str | None = None
    instance: object = None  # location's instanceId (null on a playground; what it is elsewhere: being found out)


NO_TOON = ToonInfo()
INFO_SECONDS = 1.0  # the toon, its location and Unites: read this often (laff every poll)

def at_estate(info: ToonInfo) -> bool:
    """Whether the toon is at an estate: its own or a friend's ("Doctor Pickles's Estate", read in
    game Nov 11)."""
    return (info.neighborhood or "").strip().lower().endswith("estate")


def away_from_estate(info: ToonInfo) -> bool:
    """True only when the toon is known to be somewhere that isn't an estate (unknown: False,
    so screens are read as before)."""
    return bool(info.neighborhood) and not at_estate(info)


COG_HQS = ("Sellbot HQ", "Cashbot HQ", "Lawbot HQ", "Bossbot HQ")


def in_cog_hq(info: ToonInfo) -> bool:
    """In a Cog HQ: its courtyard, a facility, a lobby or a boss (all read "<Dept> HQ" as the
    neighborhood, Nov 11)."""
    return (info.neighborhood or "").strip().lower().endswith(" hq")


def may_be_in(info: ToonInfo, *neighborhoods: str) -> bool:
    """Whether a screen that only shows in those neighborhoods can be up: True when the
    toon is in one, or when where it is isn't known (screens are read as before then)."""
    hood = (info.neighborhood or "").strip().lower()
    return not hood or hood in {n.lower() for n in neighborhoods}


def may_fish(info: ToonInfo) -> bool:
    """Ponds are on playgrounds, streets and estates: not in a Cog HQ or a cog building
    (the user, Nov 11). Not known: True."""
    if not info.neighborhood:
        return True
    return not in_cog_hq(info) and (info.zone or "").strip().lower() != "cog building"


def count_unites(unites) -> int:
    """All the Unites in /unites.json ({kind: {variant: count}})."""
    total = 0
    for variants in (unites or {}).values():
        if isinstance(variants, dict):
            total += sum(n for n in variants.values() if isinstance(n, int))
    return total


def port_of(pid: int, ports: dict[int, int]) -> int | None:
    return next((p for p, owner in sorted(ports.items()) if owner == pid), None)


def toon_name(pid: int, token_path: Path, get=get_json, ports=listening_ports, timeout: float = FIRST_TIMEOUT):
    """The name of the toon logged in on that TTR process, or None (not logged in, or
    Companion App Support off). May wait while TTR asks the player to allow the module."""
    port = port_of(pid, ports())
    if port is None:
        return None
    try:
        return get(port, "/toon.json", load_token(token_path), timeout).get("name") or None
    except Exception:  # noqa: BLE001
        return None


class ToonWatcher:
    """Polls TTR's Local API on its own thread for the TTR process `follow` names (None:
    none): laff every POLL_SECONDS, and the toon, location and Unites every INFO_SECONDS.
    `changes()` hands over the laff changes since the last call; `info` is the latest
    ToonInfo. A new toon, a max laff change, a gap in readings or a switch of process
    starts over without a change."""

    def __init__(self, token_path: Path, log=print, get=get_json, ports=listening_ports,
                 clock=time.monotonic, sleep=time.sleep, places: Path | None = None):
        """places: a file each change of place (and the API going quiet or answering again)
        is added to, kept across sessions, to learn what the location reads where."""
        self._token_path = token_path
        self._places = places
        self._place: tuple | None = None  # the last place written
        self._answering = False
        self._token: str | None = None
        self._log = log
        self._get = get
        self._ports = ports
        self._clock = clock
        self._sleep = sleep
        self._pid: int | None = None
        self._lock = threading.Lock()
        self._changes: deque[LaffChange] = deque(maxlen=20)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.info: ToonInfo = NO_TOON
        # Thread state.
        self._port: int | None = None
        self._port_pid: int | None = None
        self._allowed: set[tuple[int, int]] = set()  # (port, pid) that answered once
        self._asked: set[tuple[int, int]] = set()  # (port, pid) told about TTR's prompt
        self._last: tuple[int, int] | None = None  # (current, max)
        self._next_scan = 0.0
        self._next_info = 0.0
        self._next_token = 0.0  # the token file is looked at again then (reset from Settings)
        self._said: str | None = None
        self._named: str | None = None  # the toon name last logged (logged again only when it changes)

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="ttr-api", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def follow(self, pid: int | None) -> None:
        self._pid = pid

    def changes(self) -> list[LaffChange]:
        with self._lock:
            out = list(self._changes)
            self._changes.clear()
        return out

    def _say(self, text: str) -> None:
        if text != self._said:
            self._said = text
            self._log(text)

    def _run(self) -> None:
        while not self._stop.is_set():
            self.step()
            self._sleep(POLL_SECONDS)

    def _record(self, text: str) -> None:
        if self._places is None:
            return
        try:
            self._places.parent.mkdir(parents=True, exist_ok=True)
            with open(self._places, "a", encoding="utf-8") as out:
                out.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {text}\n")
        except OSError:
            pass

    def _quiet(self, why: str) -> None:
        if self._answering:
            self._answering = False
            self._place = None
            self._record(f"API stopped answering ({why})")

    def _forget(self) -> None:
        self._last = None
        self.info = NO_TOON
        self._next_info = 0.0

    def step(self) -> None:
        """One poll (the thread's loop body; tests call it directly)."""
        pid = self._pid
        if pid is None:
            self._port = None
            self._port_pid = None
            self._forget()
            return
        now = self._clock()
        if pid != self._port_pid or self._port is None:
            self._forget()
            if now < self._next_scan and pid == self._port_pid:
                return
            self._next_scan = now + RESCAN_SECONDS
            self._port, self._port_pid = port_of(pid, self._ports()), pid
            if self._port is None:
                self._quiet("no API port: logged out, toon selection, or the game closed")
                self._say("TTR's Companion App Support looks off (Options), or no toon is logged in: "
                          "no damage rumble or toon name.")
                return
        if self._token is None or now >= self._next_token:
            self._next_token = now + INFO_SECONDS
            token = load_token(self._token_path)  # makes a new one if Settings cleared it
            if token != self._token:
                if self._token is not None:
                    self._allowed.clear()  # TTR asks about the new one: wait for the player again
                    self._asked.clear()
                    self._log("The TTR companion token was reset; TTR will ask to allow the module again.")
                self._token = token
        first = (self._port, pid) not in self._allowed
        if first and (self._port, pid) not in self._asked:
            self._asked.add((self._port, pid))
            self._say(f"Asking TTR about the toon (port {self._port}). If TTR asks to allow {AGENT}, allow it.")
        try:
            laff = self._get(self._port, "/laff.json", self._token, FIRST_TIMEOUT if first else TIMEOUT)
            value = (int(laff["current"]), int(laff["max"]))
            if now >= self._next_info:
                self._next_info = now + INFO_SECONDS
                toon = self._get(self._port, "/toon.json", self._token, TIMEOUT)
                where = self._get(self._port, "/location.json", self._token, TIMEOUT)
                unites = self._get(self._port, "/unites.json", self._token, TIMEOUT)
                info = ToonInfo(toon.get("id"), toon.get("name"), where.get("zone"), where.get("neighborhood"),
                                count_unites(unites), where.get("district"), where.get("instanceId"))
                if not self._answering:
                    self._answering = True
                    self._record(f"API answering (port {self._port})")
                place = (info.id, info.name, info.zone, info.neighborhood, info.district, info.instance)
                if place != self._place:
                    self._place = place
                    self._record(f"{info.name} [{info.id}]  zone={info.zone!r}  neighborhood={info.neighborhood!r}  "
                                 f"district={info.district!r}  instanceId={info.instance!r}")
                if info.id != self.info.id:
                    self._last = None  # another toon: its laff isn't a change
                    with self._lock:
                        self._changes.clear()
                if info.name and info.name != self._named:
                    self._named = info.name
                    self._log(f"Toon: {info.name}.")
                self.info = info
        except Exception as error:  # noqa: BLE001 - any failure: look again later
            self._quiet(f"{type(error).__name__}: {error}")
            self._say(f"TTR's toon info didn't answer ({type(error).__name__}: {error}); trying again.")
            self._port = None
            self._forget()
            self._next_scan = now + RESCAN_SECONDS
            return
        if first:
            self._allowed.add((self._port, pid))
            self._say(f"Reading the toon from TTR (port {self._port}).")
        last, self._last = self._last, value
        if last is not None and value != last and value[1] == last[1]:
            with self._lock:
                self._changes.append(LaffChange(last[0], value[0], value[1]))
