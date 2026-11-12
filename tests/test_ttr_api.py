from ttcontroller import ttr_api
from ttcontroller.config import Config, parse, to_json
from ttcontroller.ttr_api import LaffChange, ToonWatcher, load_token, rumble_for


def test_token_is_made_once_and_kept(tmp_path):
    path = tmp_path / "token"
    first = load_token(path)
    assert len(first) == 32
    assert load_token(path) == first  # TTR asks once per value: never make a new one


def test_small_hit_is_a_short_tiny_rumble():
    low, high, ms = rumble_for(LaffChange(116, 115, 116))
    assert low < 0.25 and high < low and ms < 120


def test_rumble_grows_with_damage():
    rumbles = [rumble_for(LaffChange(116, 116 - d, 116)) for d in (1, 4, 10, 20)]
    powers = [r[0] for r in rumbles]
    lengths = [r[2] for r in rumbles]
    assert powers == sorted(powers) and lengths == sorted(lengths)
    assert rumbles[-1] == (1.0, 0.6, 500)  # 20 damage: full and long
    assert rumble_for(LaffChange(116, 66, 116)) == rumbles[-1]  # more than 20 is the same


def test_going_sad_is_the_longest():
    assert rumble_for(LaffChange(10, 0, 116)) == (1.0, 1.0, 900)


def test_laff_going_up_is_a_short_light_buzz():
    low, high, ms = rumble_for(LaffChange(100, 110, 116))
    assert low == 0 and 0 < high <= 0.5 and ms <= 150
    assert rumble_for(LaffChange(100, 101, 116)) == (low, high, ms)
    assert rumble_for(LaffChange(100, 100, 116)) is None


class FakeGame:
    def __init__(self, ports, laff):
        self.ports = ports
        self.laff = laff
        self.calls = []

    def get(self, port, path, token, timeout):
        self.calls.append((port, path, timeout))
        if isinstance(self.laff, Exception):
            raise self.laff
        return {"current": self.laff[0], "max": self.laff[1]}


def make(tmp_path, game, clock=None):
    t = [0.0]
    watcher = ToonWatcher(tmp_path / "token", log=lambda text: None, get=game.get,
                          ports=lambda: game.ports, clock=clock or (lambda: t[0]))
    return watcher, t


def test_reports_hits_from_the_followed_game(tmp_path):
    game = FakeGame({1547: 111, 1548: 222}, (116, 116))
    watcher, _ = make(tmp_path, game)
    watcher.follow(222)
    watcher.step()
    assert game.calls[0][0] == 1548  # the port that process listens on
    assert game.calls[0][2] == ttr_api.FIRST_TIMEOUT  # may wait while TTR asks the player
    assert watcher.changes() == []  # the first reading isn't a change
    game.laff = (112, 116)
    watcher.step()
    assert game.calls[-1][2] == ttr_api.TIMEOUT
    assert watcher.changes() == [LaffChange(116, 112, 116)]
    assert watcher.changes() == []


def test_max_laff_change_isnt_a_hit(tmp_path):
    game = FakeGame({1547: 111}, (116, 116))
    watcher, _ = make(tmp_path, game)
    watcher.follow(111)
    watcher.step()
    game.laff = (117, 117)  # a laff boost
    watcher.step()
    assert watcher.changes() == []


def test_not_following_reads_nothing(tmp_path):
    game = FakeGame({1547: 111}, (116, 116))
    watcher, _ = make(tmp_path, game)
    watcher.step()
    assert game.calls == []


def test_no_api_port_looks_again_later(tmp_path):
    game = FakeGame({}, (116, 116))
    watcher, t = make(tmp_path, game)
    watcher.follow(111)
    watcher.step()
    game.ports = {1547: 111}  # Companion App Support turned on
    watcher.step()
    assert game.calls == []  # not rescanned yet
    t[0] = ttr_api.RESCAN_SECONDS + 0.1
    watcher.step()
    assert game.calls and game.calls[0][0] == 1547


def test_a_gap_in_readings_starts_over(tmp_path):
    game = FakeGame({1547: 111}, (116, 116))
    watcher, t = make(tmp_path, game)
    watcher.follow(111)
    watcher.step()
    game.laff = OSError("gone")  # logging out, say
    watcher.step()
    game.laff = (50, 116)  # another toon, or later
    t[0] = ttr_api.RESCAN_SECONDS + 0.1
    watcher.step()
    assert watcher.changes() == []


def test_switching_games_starts_over(tmp_path):
    game = FakeGame({1547: 111, 1548: 222}, (116, 116))
    watcher, t = make(tmp_path, game)
    watcher.follow(111)
    watcher.step()
    game.laff = (80, 116)
    watcher.follow(222)
    watcher.step()
    assert watcher.changes() == []


def test_config_rumble_switch():
    assert Config().rumble is True
    config, warnings = parse({"rumble": False})
    assert config.rumble is False and not warnings
    assert to_json(config)["rumble"] is False
    _, warnings = parse({"rumble": "yes"})
    assert warnings


def test_listening_ports_reads_the_table():
    ports = ttr_api.listening_ports()  # real machine: whatever is listening, nothing broken
    assert all(port in ttr_api.PORTS and isinstance(pid, int) for port, pid in ports.items())


class InfoGame(FakeGame):
    """Also answers the toon, location and Unites (as TTR does, Nov 11)."""

    def __init__(self, ports, laff, toon=("TTID-TEST-0001", "Doctor Pickles"),
                 where=("Donald's Dock", "Donald's Dock"), unites=None):
        super().__init__(ports, laff)
        self.toon, self.where = toon, where
        self.unites = {"Gag-Up": {"Gag-Up Sound": 4, "Gag-Up All": 2}, "Toon-Up": {"80 Toon-Up": 5}} \
            if unites is None else unites

    def get(self, port, path, token, timeout):
        if path == "/laff.json":
            return super().get(port, path, token, timeout)
        self.calls.append((port, path, timeout))
        if path == "/toon.json":
            return {"id": self.toon[0], "name": self.toon[1], "species": "monkey"}
        if path == "/location.json":
            return {"zone": self.where[0], "neighborhood": self.where[1], "district": "Zapwood", "instanceId": None}
        if path == "/unites.json":
            return self.unites
        raise AssertionError(path)


def test_reads_the_toon_where_it_is_and_its_unites(tmp_path):
    game = InfoGame({1547: 111}, (116, 116))
    watcher, t = make(tmp_path, game)
    assert watcher.info == ttr_api.NO_TOON
    watcher.follow(111)
    watcher.step()
    assert watcher.info == ttr_api.ToonInfo("TTID-TEST-0001", "Doctor Pickles", "Donald's Dock", "Donald's Dock", 11,
                                         "Zapwood", None)
    reads = len(game.calls)
    watcher.step()  # within a second: laff only
    assert len(game.calls) == reads + 1
    t[0] = ttr_api.INFO_SECONDS + 0.1
    game.unites = {}
    watcher.step()
    assert watcher.info.unites == 0
    watcher.follow(None)  # not playing it any more: nothing known
    watcher.step()
    assert watcher.info == ttr_api.NO_TOON


def test_another_toon_on_the_same_game_isnt_a_hit(tmp_path):
    game = InfoGame({1547: 111}, (116, 116))
    watcher, t = make(tmp_path, game)
    watcher.follow(111)
    watcher.step()
    game.toon, game.laff = ("TTID-OTHER", "Other"), (40, 116)
    t[0] = ttr_api.INFO_SECONDS + 0.1
    watcher.step()
    assert watcher.info.name == "Other" and watcher.changes() == []


def test_unites_are_counted_across_kinds():
    assert ttr_api.count_unites({"Gag-Up": {"Gag-Up Sound": 4, "Gag-Up Throw": 2},
                                 "Jellybeans": {"600 jellybeans": 1}}) == 7
    assert ttr_api.count_unites({}) == 0
    assert ttr_api.count_unites(None) == 0


def test_away_from_the_estate_only_when_known():
    info = ttr_api.ToonInfo
    assert ttr_api.away_from_estate(info(neighborhood="Donald's Dock"))
    assert ttr_api.away_from_estate(info(neighborhood="Cashbot HQ"))
    assert ttr_api.away_from_estate(info(neighborhood="Chip \u2019n Dale\u2019s Acorn Acres"))
    assert not ttr_api.away_from_estate(info())  # not known: read gardening as before
    assert not ttr_api.away_from_estate(info(zone="Doctor Pickles's Estate", neighborhood="Doctor Pickles's Estate"))
    assert not ttr_api.away_from_estate(info(neighborhood="Flippy Friend's Estate"))  # a friend's


def test_toon_name_for_a_window(tmp_path):
    game = InfoGame({1547: 111}, (116, 116))
    assert ttr_api.toon_name(111, tmp_path / "token", get=game.get, ports=lambda: game.ports) == "Doctor Pickles"
    assert ttr_api.toon_name(222, tmp_path / "token", get=game.get, ports=lambda: game.ports) is None
    game_down = FakeGame({1547: 111}, OSError("toon selection"))
    assert ttr_api.toon_name(111, tmp_path / "token", get=game_down.get, ports=lambda: game_down.ports) is None


def test_places_are_written_down_across_sessions(tmp_path):
    places = tmp_path / "places.log"
    places.write_text("2026-11-10 12:00:00  an older session\n", encoding="utf-8")
    game = InfoGame({1547: 111}, (116, 116))
    t = [0.0]
    watcher = ToonWatcher(tmp_path / "token", log=lambda text: None, get=game.get, ports=lambda: game.ports,
                          clock=lambda: t[0], places=places)
    watcher.follow(111)
    watcher.step()
    t[0] = 1.1
    watcher.step()  # same place: nothing new
    game.where = ("Doctor Pickles's Estate", "Doctor Pickles's Estate")
    t[0] = 2.2
    watcher.step()
    game.ports = {}  # logged out
    game.laff = OSError("gone")
    t[0] = 3.3
    watcher.step()
    lines = places.read_text(encoding="utf-8").splitlines()
    assert lines[0].endswith("an older session")
    assert "API answering (port 1547)" in lines[1]
    assert "zone=\"Donald's Dock\"" in lines[2] and "district='Zapwood'" in lines[2] and "instanceId=None" in lines[2]
    assert "Doctor Pickles's Estate" in lines[3]
    assert "API stopped answering" in lines[4]
    assert len(lines) == 5


def test_a_big_places_log_starts_over(tmp_path, monkeypatch):
    monkeypatch.setattr(ttr_api, "PLACES_MAX_BYTES", 100)
    places = tmp_path / "places.log"
    places.write_text("x" * 101, encoding="utf-8")
    (tmp_path / "places.old.log").write_text("the oldest", encoding="utf-8")
    game = InfoGame({1547: 111}, (116, 116))
    watcher = ToonWatcher(tmp_path / "token", log=lambda text: None, get=game.get, ports=lambda: game.ports,
                          clock=lambda: 0.0, places=places)
    watcher.follow(111)
    watcher.step()
    assert (tmp_path / "places.old.log").read_text(encoding="utf-8") == "x" * 101
    assert "API answering" in places.read_text(encoding="utf-8").splitlines()[0]


def test_screens_only_where_they_show():
    info = ttr_api.ToonInfo
    street = info(zone="Loopy Lane", neighborhood="Toontown Central")
    building = info(zone="Cog Building", neighborhood="Toontown Central")
    factory = info(zone="Scrap Factory", neighborhood="Sellbot HQ")
    vp = info(zone="Sellbot Towers", neighborhood="Sellbot HQ")
    estate = info(zone="Doctor Pickles's Estate", neighborhood="Doctor Pickles's Estate")
    unknown = info()
    assert ttr_api.in_cog_hq(factory) and ttr_api.in_cog_hq(vp) and not ttr_api.in_cog_hq(street)
    assert ttr_api.may_be_in(vp, "Sellbot HQ", "Lawbot HQ")
    assert not ttr_api.may_be_in(vp, "Cashbot HQ", "Bossbot HQ")
    assert not ttr_api.may_be_in(street, "Sellbot HQ")
    assert ttr_api.may_be_in(unknown, "Bossbot HQ")  # not known: read as before
    assert ttr_api.may_fish(street) and ttr_api.may_fish(estate) and ttr_api.may_fish(unknown)
    assert ttr_api.may_fish(info(zone="Toontown Central", neighborhood="Toontown Central"))
    assert not ttr_api.may_fish(building) and not ttr_api.may_fish(factory) and not ttr_api.may_fish(vp)


def test_the_toon_name_is_logged_once(tmp_path):
    game = InfoGame({1547: 111}, (116, 116))
    said = []
    watcher = ToonWatcher(tmp_path / "token", log=said.append, get=game.get, ports=lambda: game.ports,
                          clock=lambda: 0.0)
    for _ in range(3):
        watcher.follow(111)
        watcher.step()
        watcher.follow(None)  # TTR not in front for a moment
        watcher.step()
    assert [s for s in said if s.startswith("Toon:")] == ["Toon: Doctor Pickles."]


def test_clearing_the_token_makes_a_new_one(tmp_path):
    path = tmp_path / ttr_api.TOKEN_FILE
    first = load_token(path)
    assert ttr_api.clear_token(path) and not path.exists()
    assert not ttr_api.clear_token(path)  # nothing left to clear
    assert load_token(path) != first


def test_a_running_watcher_picks_up_a_reset_token(tmp_path):
    game = FakeGame({1547: 111}, (116, 116))
    said = []
    t = [0.0]
    watcher = ToonWatcher(tmp_path / "token", log=said.append, get=game.get, ports=lambda: game.ports,
                          clock=lambda: t[0])
    watcher.follow(111)
    watcher.step()
    old = watcher._token
    t[0] = 0.5
    watcher.step()
    assert game.calls[-1][2] == ttr_api.TIMEOUT
    ttr_api.clear_token(tmp_path / "token")  # Settings' reset button
    t[0] = ttr_api.INFO_SECONDS + 0.1
    watcher.step()
    assert watcher._token != old
    laff = [c for c in game.calls if c[1] == "/laff.json"]
    assert laff[-1][2] == ttr_api.FIRST_TIMEOUT  # waits while TTR asks the player again
    assert any("reset" in s for s in said)
