"""M11 hints: which controller buttons to show where, on each screen.

The look (chosen from the hints sample kit, Nov 2026):
- A small Xbox button sprite as a corner badge on each on-screen button it presses.
- Labeled popup buttons (OK/Cancel, Yes/No...) are fully covered by their controller
  button, so TTR's check and X can't be seen.
- A small bar tucked under a panel for the few things with no on-screen button that a
  player wouldn't guess (never plain move/select).
- Navigation (LB/RB pages, LT/RT tabs) sits outside the thing it moves through.
- Pairs mirror each other (left one top-left, right one top-right).
- A gold ring only on hold-to-act buttons.

This module only decides what goes where (as ui.UIPoints, so it works at any window
size); hint_draw.py draws it. Positions were measured on the mockups at 1920x1009 and
are kept relative to the button they belong to wherever a reader or a module constant
knows that button.

Hints on the screens whose buttons the config can remap (walking, battle, shop, NPC
chat, SpeedChat, friends, the book) name the action they stand for; `hints_for` swaps
in whatever button the config gives that action (or drops the hint when nothing does).
The rest (start-up, Make-a-Toon, TTR's Options, gardening, the mailbox...) have fixed
buttons, so their hints are fixed too.
"""

from dataclasses import dataclass, field
from functools import cache

from . import ui
from .bindings import Bindings
from .battle import (PASS, RUN, RUN_NO, RUN_YES, SOS_FILTER, TARGET_BACK, TRUNK, WAITING_BACK, BattleScreen,
                     default_battle_bindings)
from .book import (BACK_TO_PLAYGROUND, COLOR_LEFT, COLOR_RIGHT, GO_HOME, SNAPSHOT_ARROWS, SNAPSHOT_TRASH, SUIT_ICONS,
                   TELEPORT as DISTRICT_TELEPORT, BookScreen, default_book_bindings)
from .boarding import BoardingScreen
from .facility import CLOSE as FACILITY_CLOSE, TELEPORT as FACILITY_TELEPORT, FacilityScreen
from .fishing import CARD_KEEP, CARD_RELEASE, CAST, EXIT as FISHING_EXIT, FishingScreen
from .friends import FriendsScreen, default_friends_bindings
from .garden import PLANT, PLANT_CANCEL, PLANT_RESET, SELL_ALL, SELL_CANCEL, GardenScreen
from .garden_intro import DONE as INTRO_DONE, NEXT as INTRO_NEXT, PREVIOUS as INTRO_PREVIOUS, GardenIntro
from .mailbox import (CLOSE as MAILBOX_CLOSE, DISCARD as MAILBOX_DISCARD, LEFT as MAILBOX_LEFT,
                      RIGHT as MAILBOX_RIGHT, TAKE as MAILBOX_TAKE, MailboxScreen)
from .makeatoon import BACK as MAT_BACK, CLOSE as MAT_CLOSE, MakeAToonScreen
from .mapper import default_bindings
from .npc import NpcScreen, default_npc_bindings
from .options import CLOSE as OPTIONS_CLOSE, OptionsScreen
from .pregame import NAME_BUTTONS, OPTIONS as PREGAME_OPTIONS, QUIT, TRASH as TOON_TRASH, TYPE_CANCEL, TYPE_OK, PregameScreen
from .shop import DONE, EXIT, LOAD_PRESET, SAVE_PRESET, TRASH as SHOP_TRASH, ShopScreen, default_shop_bindings
from .speedchat import default_speedchat_bindings
from .silly import CARD_X, DETAILS_BUTTON, SillyScreen
from .ui import FRIENDS_CLOSE, UIPoint

_W, _H, _U = 1920, 1009, 1009  # the mockups' size, and its unit (the shorter side)

S = 0.045  # a navigation icon's height, in units of the shorter side
BADGE = S * 0.85  # a corner badge's
COVER = 0.058  # a popup button's cover (TTR's standard round OK and Cancel)
BAR = S * 0.75  # a bar's icons


@dataclass(frozen=True)
class Badge:
    """A controller button sprite centered on `at`. sprite: "A", "B", ..., "LB", "LT",
    "START", "VIEW", D-pad "DL"/"DR"/"DU"/"DD"/"DUD"/"DLR"/"D4", sticks "L"/"R"/"LS"/"RS"
    with optional arrows after a colon ("R:ud"). size: its height, in units of the
    shorter side. cover: sits right on a popup button (no shadow). hold: the gold ring.
    act: the remappable action it stands for, as (table, actions, hold), or () when its
    button is fixed; `sprite` is then the default button's, swapped by `hints_for`."""
    sprite: str
    at: UIPoint
    size: float = BADGE
    hold: bool = False
    cover: bool = False
    act: tuple = ()


@dataclass(frozen=True)
class Bar:
    """A small prompt bar centered on `at`: (sprite, label) pairs. Before `hints_for`
    resolves them, an item may carry a third part, its act (as on Badge)."""
    items: tuple[tuple[str, str], ...]
    at: UIPoint
    size: float = BAR


def _px(x: float, y: float, h: str = "center", v: str = "center") -> UIPoint:
    """A point measured in pixels on a 1920x1009 mockup, kept from the given anchors."""
    bx = {"left": 0.0, "center": _W / 2, "right": float(_W)}[h]
    by = {"top": 0.0, "center": _H / 2, "bottom": float(_H)}[v]
    return UIPoint(h, (x - bx) / _U, (y - by) / _U, v)


def _by(p: UIPoint, dx: float, dy: float) -> UIPoint:
    """`p` moved by mockup pixels (at 1920x1009)."""
    return p.offset(dx / _U, dy / _U)


def _badge(sprite: str, p: UIPoint, dx: float = 0, dy: float = 0, scale: float = 1.0, hold: bool = False,
           act: tuple = ()) -> Badge:
    return Badge(sprite, _by(p, dx, dy), BADGE * scale, hold, act=act)


def _cover(sprite: str, p: UIPoint, size: float = COVER, act: tuple = ()) -> Badge:
    return Badge(sprite, p, size, cover=True, act=act)


def _covers(dialog, first: str = "A", second: str = "B", acts: tuple = ((), ())) -> list[Badge]:
    """An OK/Cancel pair's covers. Either may be missing; the same point twice is an OK
    alone (both buttons press it), shown as the first."""
    ok, cancel = dialog
    if ok is not None and ok == cancel:
        return [_cover(first, ok, act=acts[0])]
    out = []
    if ok is not None:
        out.append(_cover(first, ok, act=acts[0]))
    if cancel is not None:
        out.append(_cover(second, cancel, act=acts[1]))
    return out


# The acts of the remappable tables: (table, actions, hold).
def _walk(*actions: str, hold: bool = False) -> tuple:
    return ("overworld", actions, hold)


def _bt(*actions: str, hold: bool = False) -> tuple:
    return ("battle", actions, hold)


def _sh(*actions: str) -> tuple:
    return ("shop", actions, False)


def _fr(*actions: str) -> tuple:
    return ("friends", actions, False)


def _np(*actions: str) -> tuple:
    return ("npc", actions, False)


def _bk(*actions: str) -> tuple:
    return ("book", actions, False)


_DIRS4 = ("up", "down", "left", "right")


@dataclass(frozen=True)
class Context:
    """What's showing, as app.py decides it. mode: the screen that owns the controller:
    "options", "mat", "pregame", "battle", "shop", "speedchat", "friends", "npc", "book",
    "golf" (the golf green), "fishing" (on a dock) or "free" (walking around, maybe with a
    small panel up)."""
    mode: str = "free"
    options: OptionsScreen = field(default_factory=OptionsScreen)
    options_row_y: float | None = None  # TTR's Options: the hovered row
    mat: MakeAToonScreen = field(default_factory=MakeAToonScreen)
    pregame: PregameScreen = field(default_factory=PregameScreen)
    toon_slot: int | None = None  # toon selection: the hovered toon
    battle: BattleScreen = field(default_factory=BattleScreen)
    shop: ShopScreen = field(default_factory=ShopScreen)
    friends: FriendsScreen = field(default_factory=FriendsScreen)
    npc: NpcScreen = field(default_factory=NpcScreen)
    book: BookScreen = field(default_factory=BookScreen)
    book_task: int | None = None  # the ToonTasks page: the hovered task
    fishing: FishingScreen = field(default_factory=FishingScreen)
    fishing_cast: str = "move"  # how the stick casts ("move" or "stick")
    garden: GardenScreen = field(default_factory=GardenScreen)
    garden_intro: GardenIntro = field(default_factory=GardenIntro)
    mailbox: MailboxScreen = field(default_factory=MailboxScreen)
    facility: FacilityScreen = field(default_factory=FacilityScreen)
    silly: SillyScreen = field(default_factory=SillyScreen)
    boarding: BoardingScreen = field(default_factory=BoardingScreen)
    dialog: tuple[UIPoint, UIPoint] | None = None  # an OK/Cancel no screen owns
    mail_close: UIPoint | None = None  # Clarabelle's popup's X
    mail_icon: UIPoint | None = None  # Clarabelle's icon, when she's up (the Silly Meter's gauge is in c.silly)
    hop_off: UIPoint | None = None  # in an elevator or golf kart
    leave: UIPoint | None = None  # on a CEO golf ball or seltzer bottle, or a CFO crane
    hud: bool = False  # the gags/trunk/tasks HUD is up (kept up by toggle_hud)
    walking_bar: bool = True  # the walking bar (its own setting)
    # The config's remappable tables: "overworld", "battle", "shop", "npc", "speedchat",
    # "friends", "book" (missing ones are the defaults).
    tables: dict | None = field(default=None, compare=False)


# ---- walking around -----------------------------------------------------------------
WALK_BADGES = (
    _badge("VIEW", _px(126, 58, "left", "top"), scale=0.8, act=_walk("speedchat")),  # the green speedchat button
    _badge("RB", _px(1812, 98, "right", "top"), scale=0.8, act=_walk("friendsList")),  # friends
    _badge("START", _px(1838, 912, "right", "bottom"), scale=0.8, act=_walk("stickerBook")),  # the book
)
WALK_BAR = Bar((("L", "Walk"), ("A", "Jump", _walk("jump")), ("Y", "Gags", _walk("showGags")),
                ("X", "Tasks", _walk("showTasks")), ("DU", "Map", _walk("showMap")), ("LT", "Unite", _walk("unite"))),
               _px(560, 985, "left", "bottom"), S * 0.6)


def _free(c: Context) -> list:
    if c.dialog is not None:
        ok, cancel = c.dialog
        return [_cover("B", cancel)] if ok == cancel else _covers(c.dialog)
    if c.garden_intro.is_open:
        i = c.garden_intro
        out = [_badge("B", INTRO_PREVIOUS, -34, -30)] if i.previous else []
        if i.done:
            out.append(_badge("A", INTRO_DONE, -34, -30))
        elif i.next:
            out.append(_badge("A", INTRO_NEXT, -34, -30))
        return out
    g = c.garden
    if g.selling:
        return [_cover("B", SELL_CANCEL), _cover("A", SELL_ALL)]
    if g.ok is not None:
        return [_cover("A", g.ok)]
    if g.planting:
        return [_cover("B", PLANT_CANCEL), _cover("X", PLANT_RESET), _cover("Y", PLANT),
                Bar((("DLR", "Beans"), ("A", "Select"), ("DU", "Last flower")), _px(960, 760))]
    if c.mailbox.is_open:
        return [_badge("DL", MAILBOX_LEFT, -62, -45), _badge("DR", MAILBOX_RIGHT, 52, -45),
                _badge("A", MAILBOX_TAKE, -60, -35), _badge("X", MAILBOX_DISCARD, -60, -34),
                _badge("B", MAILBOX_CLOSE, -115, 2)]
    if c.facility.popup:
        return [_badge("A", FACILITY_TELEPORT, -42, -38), _badge("B", FACILITY_CLOSE, -21, -17, 0.8),
                Bar((("LB", "Previous"), ("RB", "Next")), _px(1790, 452, "right", "top"))]
    if c.silly.card:
        return [_badge("DL", DETAILS_BUTTON, -20, -21, 0.9), _badge("B", CARD_X, -20, -19, 0.9)]
    if c.mail_close is not None:
        return [_badge("RT", c.mail_close, -22, -20, act=_walk("mail"))]
    if c.hop_off is not None:
        return [_badge("B", c.hop_off, -142, 0, scale=2.0, act=_walk("back"))]  # big, on Hop off's left end
    if c.leave is not None:
        return [_cover("B", c.leave, 0.125, act=_walk("back")),
                Bar((("L", "Turn"), ("A", "Charge", _walk("jump"))), _px(960, 905, "center", "bottom"))]
    if c.boarding.kind == "open" and c.boarding.leave is not None:
        return [_badge("B", c.boarding.leave, -16, -16, 0.9, hold=True),
                Bar((("DUD", "Move"), ("A", "Select"), ("R:l", "Close")), _by(c.boarding.leave, -107, 104), S * 0.65)]
    out: list = list(WALK_BADGES)
    # Clarabelle's icon and the Silly Meter's gauge share the slot left of the friends
    # icon (one moves over when both are up), so each badge goes where its reader found
    # it: RT on Clarabelle, a held RT on the gauge. Bottom-left of each icon.
    if c.mail_icon is not None:
        out.append(_badge("RT", c.mail_icon, -40, 40, 0.8, act=_walk("mail")))
    if c.silly.icon is not None:
        out.append(_badge("RT", c.silly.icon, -40, 40, 0.8, hold=True, act=_walk("sillyMeter", hold=True)))
    if g.top is not None or g.bottom is not None:
        # The gardening panel's buttons take Y and X, so the walking bar would be wrong.
        out += [_badge("Y", g.top, -36, -34)] if g.top is not None else []
        out += [_badge("X", g.bottom, -36, -35)] if g.bottom is not None else []
    elif c.walking_bar and not c.hud:
        out.append(WALK_BAR)
    return out


# ---- battle ---------------------------------------------------------------------------
_PASS_Y = _badge("Y", PASS, -35, -28, act=_bt("pass"))
_RUN_B = _badge("B", RUN, -35, -28, hold=True, act=_bt("run", hold=True))
_TRUNK_X = _badge("X", TRUNK, -77, -40, act=_bt("trunk"))
_BATTLE_MOVE = ("D4", "Move", _bt(*_DIRS4))
_BATTLE_SELECT = ("A", "Select", _bt("select"))
_TEAMMATES = ("LB", "Teammates", _bt("teammates"))


def _battle(c: Context) -> list:
    s = c.battle
    if s.kind == "picker":
        if s.close is not None:  # planting a gag tree, not a battle
            return [_badge("B", s.close, -20, -20, act=_bt("back"))]
        return [_PASS_Y, _RUN_B, _TRUNK_X, Bar((_BATTLE_MOVE, _BATTLE_SELECT, _TEAMMATES), _px(960, 790))]
    if s.kind == "trunk":
        return [_PASS_Y, _TRUNK_X, _badge("LS", SOS_FILTER, -89, 1, 0.9, act=_bt("sos_filter")),
                Bar((_BATTLE_MOVE, _BATTLE_SELECT, ("R:ud", "Scroll", _bt("sos_scroll_up", "sos_scroll_down")),
                     _TEAMMATES), _px(960, 790))]
    if s.kind == "target":
        return [_badge("B", TARGET_BACK, -37, -30, act=_bt("back"))]
    if s.kind == "waiting":
        return [_badge("B", WAITING_BACK, -33, -26, act=_bt("back")),
                Bar((("DLR", "Teammates' gags", _bt("left", "right")),), _px(955, 680))]
    if s.kind == "confirm_run":
        return _covers((RUN_YES, RUN_NO), acts=(_bt("select"), _bt("back")))
    return []


# ---- the gag shop ---------------------------------------------------------------------
def _shop(c: Context) -> list:
    s = c.shop
    if s.kind == "dialog":
        return _covers((s.ok, s.cancel), acts=(_sh("select"), _sh("back")))
    if s.kind != "shop":
        return []
    out = [_badge("X", SHOP_TRASH, -27, -40, act=_sh("delete_mode"))]
    if s.trolley:
        out += [_badge("B", EXIT, -87, -41, act=_sh("back")), _badge("RT", DONE, -87, -40, act=_sh("play_again"))]
    else:
        out += [_badge("LB", SAVE_PRESET, -28, -21, 0.8, act=_sh("save_preset")),
                _badge("RB", LOAD_PRESET, -28, -21, 0.8, act=_sh("load_preset")),
                _badge("B", DONE, -87, -40, act=_sh("back"))]
    one, most = ("Delete one", "Delete all") if s.delete_mode else ("Buy one", "Buy max")
    out.append(Bar((("D4", "Move", _sh(*_DIRS4)), ("A", one, _sh("select")), ("Y", most, _sh("buy_max"))),
                   _px(960, 752)))
    return out


# ---- menus over the game --------------------------------------------------------------
def _friends(c: Context) -> list:
    s = c.friends
    if s.kind == "list":
        return [_badge("DL", _px(1708, 404, "right", "top"), scale=0.8, act=_fr("left")),
                _badge("DR", _px(1900, 404, "right", "top"), scale=0.8, act=_fr("right")),
                _badge("B", FRIENDS_CLOSE.center, -19, -21, 0.8, act=_fr("back")),
                Bar((("X", "Go To", _fr("goTo")), ("Y", "Whisper", _fr("whisper"))),
                    _px(1805, 478, "right", "top"), S * 0.65)]
    if s.kind == "panel":
        return [_badge("X", _px(1738, 238, "right", "top"), scale=0.8, act=_fr("goTo")),
                _badge("Y", _px(1738, 281, "right", "top"), scale=0.8, act=_fr("whisper")),
                _badge("B", _px(1868, 412, "right", "top"), scale=0.8, act=_fr("back"))]
    if s.kind == "popup":
        return _covers((s.yes, s.no), acts=(_fr("select"), _fr("back")))
    return []


def _npc(c: Context) -> list:
    s = c.npc
    if s.kind == "dialogue" and s.button is not None:
        return [_cover("A", s.button, 0.045, act=_np("select"))]  # the bubble's little next arrow
    if s.kind == "tasks" and s.cancel is not None:
        return [_badge("B", s.cancel, -66, -17, act=_np("back")),
                Bar((("DUD", "Choose", _np("up", "down")), ("A", "Select", _np("select"))), _by(s.cancel, 312, 60))]
    return []


def _options(c: Context) -> list:
    s = c.options
    if s.kind == "dialog" and s.dialog is not None:
        return _covers(s.dialog)
    if s.kind != "options":
        return []
    out = [Badge("LT", _px(520, 160), S), Badge("RT", _px(1400, 160), S), _badge("B", OPTIONS_CLOSE, -27, -22, 0.9),
           Badge("R:ud", _px(1404, 578), S * 0.85)]  # right of the scroll bar, centered on it
    for row in s.rows:
        if row.y == c.options_row_y and row.help is not None:
            out.append(_badge("Y", row.help, -21, -15, 0.8))
    return out


# ---- the shticker book ----------------------------------------------------------------
BOOK_NAV = (Badge("LB", _px(525, 850), S * 0.7, act=_bk("prevPage")),  # under the page corners
            Badge("RB", _px(1393, 850), S * 0.7, act=_bk("nextPage")),
            _badge("B", _px(1790, 885, "right", "bottom"), act=_bk("close")))  # the book icon closes it


def _book(c: Context) -> list:
    s = c.book
    if s.dialog is not None:
        return _covers(s.dialog, acts=(_bk("select"), _bk("close")))
    out = list(BOOK_NAV)
    if len(s.top_tabs) > 1:  # tabs along the top: LT/RT out past their ends
        out += [Badge("LT", _by(s.top_tabs[0], -140, 7), S, act=_bk("prevTab")),
                Badge("RT", _by(s.top_tabs[-1], 140, 7), S, act=_bk("nextTab"))]
    if s.page == "map":
        out += [_badge("Y", GO_HOME, -43, -34, 0.9, act=_bk("goHome"))] if s.go_home else []
        out += [_badge("X", BACK_TO_PLAYGROUND, -106, -34, 0.9, act=_bk("pageAction"))] if s.back_to_playground else []
    elif s.page == "districts":
        out.append(_badge("A", DISTRICT_TELEPORT, -40, -40, act=_bk("select")))
    elif s.page == "cog gallery" and not s.summons_open:
        # The suit icons down the left: the right stick, pointed each one's way, in the
        # page margin left of the icon and level with it.
        for direction, action in (("up", "stickUp"), ("left", "stickLeft"), ("right", "stickRight"),
                                  ("down", "stickDown")):
            out.append(_badge(f"R:{direction[0]}", SUIT_ICONS[direction], -62, 0, 0.9, act=_bk(action)))
    elif s.page == "toontasks" and c.book_task is not None and c.book_task < len(s.tasks):
        trash = s.tasks[c.book_task]
        if isinstance(trash, UIPoint):
            out.append(_badge("X", trash, -14, -14, 0.8, act=_bk("pageAction")))
    elif s.page == "options":
        out += [_badge("DL", COLOR_LEFT, -18, -17, 0.9, act=_bk("left")),
                _badge("DR", COLOR_RIGHT, 18, -17, 0.9, act=_bk("right"))]
    elif s.page == "snapshots":
        left, right = SNAPSHOT_ARROWS["left"], SNAPSHOT_ARROWS["right"]
        out += [_badge("DL", left, -19, -18, 0.9, act=_bk("left"))] if "left" in s.snapshot_arrows else []
        out += [_badge("DR", right, 20, -18, 0.9, act=_bk("right"))] if "right" in s.snapshot_arrows else []
        out += [_badge("X", SNAPSHOT_TRASH, -17, -24, 0.9, act=_bk("pageAction"))] if s.snapshot_trash else []
    return out


# ---- start-up, toon selection, Make-a-Toon -------------------------------------------------
_QUIT_B = _badge("B", QUIT, -88, -18, hold=True)
_OPTIONS_START = _badge("START", PREGAME_OPTIONS, -16, -28, 0.85)  # TTR's Options icon, beside QUIT


def _pregame(c: Context) -> list:
    s = c.pregame
    if s.kind == "startup":
        return [_QUIT_B, _OPTIONS_START]
    if s.kind == "toons":
        out = [_QUIT_B, _OPTIONS_START]
        i = c.toon_slot
        if i is not None and i < len(s.trash) and s.trash[i]:
            out.append(_badge("X", TOON_TRASH[i], -20, -20, 0.8))
        if i is not None and i < len(s.names) and s.names[i]:
            out.append(_badge("Y", NAME_BUTTONS[i], -82, -24, 0.8))
        return out
    if s.kind == "confirm" and s.dialog is not None:
        return _covers(s.dialog)
    if s.kind == "type":
        return [_cover("Y", TYPE_OK), _cover("B", TYPE_CANCEL)]  # only Y presses OK here
    return []


def _mat(c: Context) -> list:
    s = c.mat
    if s.kind in ("confirm", "submission") and len(s.buttons) >= 2:
        return _covers((s.buttons[0], s.buttons[1]))
    out = []
    if s.kind == "style":
        out.append(_badge("B", MAT_CLOSE, -25, -29))  # cancels only on the first step
    if s.back is not None and s.kind != "style":
        out.append(_badge("LB", s.back, -26, -29, 0.8))
    if s.kind in ("style", "type", "color", "clothes"):
        if s.next is not None:
            out.append(_badge("RB", s.next, 27, -29, 0.8))
        for row in s.rows:
            if row.shuffle:
                out.append(_badge("X", row.point, -79, -19, 0.9))
        if s.kind != "style":
            out.append(Badge("R:lr", _px(960, 940, "center", "bottom"), S * 0.85))  # turn the toon
    elif s.kind == "name":
        if s.done is not None:
            out.append(_badge("START", s.done, -27, -27, 0.8))
        if s.next is not None:
            out.append(_badge("RT", s.next, -27, -27, 0.8))
        if len(s.buttons) >= 2:
            out += [_badge("X", s.buttons[0], -116, -19, 0.9), _badge("Y", s.buttons[1], -114, -20, 0.9)]
    return out


# ---- fishing (M14) -------------------------------------------------------------------
def _fishing(c: Context) -> list:
    if c.fishing.kind == "card":
        # A still casts with the card up (the user, Nov 9).
        out = [_cover("X", CARD_KEEP, 0.04), _cover("B", CARD_RELEASE, 0.04)]
    else:
        out = [_badge("B", FISHING_EXIT, -30, -28)]
    if c.fishing.can_cast:
        out += [_badge("A", CAST, -40, -32),
                Bar((("A", "Hold to cast"), ("L", "Move the aim" if c.fishing_cast == "move" else "Pull back to aim"),
                     ("LS", "Switch")), _px(960, 985, "center", "bottom"), S * 0.6)]
    return out


_MODES = {"free": _free, "fishing": _fishing, "battle": _battle, "shop": _shop, "friends": _friends, "npc": _npc,
          "options": _options, "book": _book, "pregame": _pregame, "mat": _mat}


def hints_for(c: Context) -> tuple:
    """The hints for what's showing: Badges and Bars, with the config's buttons."""
    make = _MODES.get(c.mode)
    if not make:
        return ()
    tables = {**default_tables(), **(c.tables or {})}
    out = []
    for hint in make(c):
        if isinstance(hint, Bar):
            items = []
            for item in hint.items:
                sprite = _sprite_for(tables, item[2], item[0]) if len(item) > 2 else item[0]
                if sprite is not None:
                    items.append((sprite, item[1]))
            if items:
                out.append(Bar(tuple(items), hint.at, hint.size))
        elif hint.act:
            sprite = _sprite_for(tables, hint.act, hint.sprite)
            if sprite is not None:
                out.append(Badge(sprite, hint.at, hint.size, hint.hold, hint.cover, hint.act))
        else:
            out.append(hint)
    return tuple(out)


@cache
def default_tables() -> dict[str, Bindings]:
    return {"overworld": default_bindings(), "battle": default_battle_bindings(), "shop": default_shop_bindings(),
            "npc": default_npc_bindings(), "speedchat": default_speedchat_bindings(),
            "friends": default_friends_bindings(), "book": default_book_bindings()}


_BUTTON_SPRITE = {"a": "A", "b": "B", "x": "X", "y": "Y", "lb": "LB", "rb": "RB", "lt": "LT", "rt": "RT",
                  "start": "START", "view": "VIEW", "ls": "LS", "rs": "RS"}
_DPAD_SPRITE = {"u": "DU", "d": "DD", "l": "DL", "r": "DR", "ud": "DUD", "lr": "DLR", "udlr": "D4"}
_FAMILY = {"dpad_": "D", "ls_": "L", "rs_": "R"}


def _family(button: str) -> tuple[str, str] | None:
    """A direction button's family ("D", "L" or "R") and its letter (u, d, l, r)."""
    for prefix, family in _FAMILY.items():
        if button.startswith(prefix):
            return family, button[len(prefix)]
    return None


def _direction_sprite(family: str, letters: str) -> str:
    letters = "".join(c for c in "udlr" if c in letters)
    if family == "D":
        return _DPAD_SPRITE.get(letters, "D4")
    return f"{family}:{letters}"


def _sprite_for(tables: dict[str, Bindings], act: tuple, default: str) -> str | None:
    """The sprite for an act with these bindings: the default while its buttons still do
    it, else the first button that does (a direction set drawn as one D-pad or stick),
    or None when no button does."""
    table, actions, hold = act
    bindings = tables.get(table)
    if bindings is None:
        return default
    mapping = bindings.hold if hold else bindings.press
    bound = [[b for b, a in mapping.items() if a == action] for action in actions]
    want = sprite_buttons(default)
    if (want and all(mapping.get(b) in actions for b in want)
            and all(any(b in want for b in buttons) for buttons in bound if buttons)):
        return default
    first = next((buttons[0] for buttons in bound if buttons), None)
    if first is None:
        return None
    if _family(first) is None:
        return _BUTTON_SPRITE.get(first)
    family = _family(first)[0]
    letters = "".join(f[1] for buttons in bound for b in buttons if (f := _family(b)) and f[0] == family)
    return _direction_sprite(family, letters)


# Which controller buttons each sprite stands for, so pressing one bounces its badge.
_SPRITE_BUTTONS = {
    "A": ("a",), "B": ("b",), "X": ("x",), "Y": ("y",), "LB": ("lb",), "RB": ("rb",), "LT": ("lt",),
    "RT": ("rt",), "START": ("start",), "VIEW": ("view",), "LS": ("ls",), "RS": ("rs",),
    "DL": ("dpad_left",), "DR": ("dpad_right",), "DU": ("dpad_up",), "DD": ("dpad_down",),
    "DUD": ("dpad_up", "dpad_down"), "DLR": ("dpad_left", "dpad_right"),
    "D4": ("dpad_up", "dpad_down", "dpad_left", "dpad_right"),
    "L": ("ls_up", "ls_down", "ls_left", "ls_right"), "R": ("rs_up", "rs_down", "rs_left", "rs_right"),
}


_DIRECTION_NAMES = {"u": "up", "d": "down", "l": "left", "r": "right"}


def sprite_buttons(sprite: str) -> tuple[str, ...]:
    base, _, arrows = sprite.partition(":")
    if base in ("L", "R") and arrows:  # just the arrowed directions
        letters = {"ud": "ud", "lr": "lr", "4": "udlr"}.get(arrows, arrows)
        return tuple(f"{base.lower()}s_{_DIRECTION_NAMES[c]}" for c in letters if c in _DIRECTION_NAMES)
    return _SPRITE_BUTTONS.get(base, ())
