"""Reading the TTR window: every screen reader, in order, on one frame (`read_all`), and a
thread that does it away from the controller loop (`ReadWorker`).

The readers take 20 to 60 ms together on a big window (the NPC bubble search, the book,
speedchat and Clarabelle's popup are the slow ones), and a window capture waits for TTR's
next frame. On the controller loop's own thread that stalled the controller ten times a
second; on this one, Python switches back to the loop every few milliseconds.

The order matters (screens fool each other, CLAUDE.md): TTR's Options window is over
everything, then Make-a-Toon and the pre-game screens, then the book (its pages look like
other screens), then battles, the gag shop and the rest, with speedchat and the friends
list last (they open over battles and the book).

Each reader runs through a `Guard`: one that raises (a window size nobody measured) is
logged once and reads as "not showing", instead of stopping the controller.
"""

import threading
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field

from . import ui
from .battle import BattleScreen, read_screen
from .boarding import BoardingScreen, read_boarding
from .book import BookScreen, read_book
from .ceo import read_leave
from .dialog import find_cancel_alone, find_ok_cancel
from .elevator import read_hop_off
from .facility import FacilityScreen, read_facility
from .fishing import FishingScreen, read_fishing
from .friends import FriendsScreen, read_friends
from .garden import GardenScreen, read_garden
from .garden_intro import GardenIntro, read_garden_intro
from .golf_green import GolfGreenScreen, read_golf_green
from .hud import HudScreen, read_hud
from .mail import read_mail
from .mailbox import MailboxScreen, read_mailbox
from .makeatoon import MakeAToonScreen, read_make_a_toon
from .npc import NpcScreen, read_npc
from .options import OptionsScreen, read_options
from .pregame import PregameScreen, read_pregame
from .screen import Frame
from .shop import ShopScreen, read_shop
from .silly import SillyScreen, read_silly
from .speedchat import SpeedchatScreen, read_speedchat
from .vp import read_pie_round


@dataclass(frozen=True)
class Gates:
    """What the controller loop knows that decides which readers run (TTR's Local API's
    place, the HUD panels shown, what the mappers expect). Unknown places: True."""
    estate: bool = True  # gardening, its introduction and the mailbox
    cog_hq: bool = True  # facility nametags
    pies: bool = True  # the VP's pie round, the CJ's evidence round
    leave: bool = True  # a CFO crane's or CEO seltzer/golf ball's leave button (its hint)
    golf: bool = True  # the Cog Golf green
    fish: bool = True  # a pond's dock
    hud_gags: bool = False  # the gags HUD is shown (toggle_hud)
    hud_tasks: bool = False  # the tasks HUD is shown
    look_for_unite: bool = False  # speedchat: look for the Unite menu
    friends_dialogs: bool = False  # the friends list: a dialog may come up
    hints: bool = False  # the hints are drawn: read what only they need


@dataclass(frozen=True)
class Reads:
    """What every reader saw on one frame (a screen that isn't showing reads as its
    default). Reads() is "nothing read yet", as after a pause."""
    options: OptionsScreen = field(default_factory=OptionsScreen)
    mat: MakeAToonScreen = field(default_factory=MakeAToonScreen)
    pregame: PregameScreen = field(default_factory=PregameScreen)
    book: BookScreen = field(default_factory=BookScreen)
    battle: BattleScreen = field(default_factory=BattleScreen)
    # An OK/Cancel dialog nothing else owns: its OK and Cancel (Cancel twice for a
    # Cancel-only dialog), else None.
    stray_dialog: tuple[ui.UIPoint, ui.UIPoint] | None = None
    shop: ShopScreen = field(default_factory=ShopScreen)
    hud: HudScreen = field(default_factory=HudScreen)
    garden: GardenScreen = field(default_factory=GardenScreen)
    garden_intro: GardenIntro = field(default_factory=GardenIntro)
    mailbox: MailboxScreen = field(default_factory=MailboxScreen)
    boarding: BoardingScreen = field(default_factory=BoardingScreen)
    silly: SillyScreen = field(default_factory=SillyScreen)
    golf: GolfGreenScreen = field(default_factory=GolfGreenScreen)
    fishing: FishingScreen = field(default_factory=FishingScreen)
    facility: FacilityScreen = field(default_factory=FacilityScreen)
    npc: NpcScreen = field(default_factory=NpcScreen)
    speedchat: SpeedchatScreen = field(default_factory=SpeedchatScreen)
    friends: FriendsScreen = field(default_factory=FriendsScreen)
    pies: bool = False  # the VP's pie round or the CJ's evidence round
    # Read for the hints only (the overworld reads these on a press).
    hint_mail_close: ui.UIPoint | None = None  # Clarabelle's popup's X
    hint_mail_icon: ui.UIPoint | None = None  # Clarabelle's icon
    hint_hop: ui.UIPoint | None = None  # an elevator's or golf kart's Hop off
    hint_leave: ui.UIPoint | None = None  # a CFO crane's or CEO seltzer/golf ball's leave button
    hint_friends: bool = True  # the friends button is showing (a timer can take its place)
    hint_book: bool = True  # the shticker book's button is showing (else just Options')

    @property
    def in_game(self) -> bool:
        return self.pregame.kind is None and self.options.kind is None and self.mat.kind is None


class Guard:
    """Runs a reader; one that raises is logged (once per reader and error) and reads as
    its default."""

    def __init__(self, log: Callable[[str], None], debug: bool = False):
        self._log, self._debug = log, debug
        self._seen: set[tuple[str, str]] = set()

    def __call__(self, name: str, default, reader, *args):
        try:
            return reader(*args)
        except Exception as e:  # noqa: BLE001 (a reader's bug mustn't stop the controller)
            key = (name, type(e).__name__)
            if key not in self._seen:
                self._seen.add(key)
                self._log(f"Note: the {name} reader failed ({type(e).__name__}: {e}); it reads as not "
                          "showing. Please report this with the log.")
                if self._debug:
                    self._log(traceback.format_exc().rstrip())
            return default


def read_all(frame: Frame, gates: Gates, guard: Guard) -> Reads:
    """Every reader, in order, each skipped when an earlier one rules its screen out."""
    w, h, px = frame.width, frame.height, frame.get_pixel
    options = guard("Options", OptionsScreen(), read_options, w, h, px)
    mat = guard("Make-a-Toon", MakeAToonScreen(), read_make_a_toon, w, h, px) if options.kind is None else MakeAToonScreen()
    pregame = (guard("pre-game", PregameScreen(), read_pregame, w, h, px)
               if options.kind is None and mat.kind is None else PregameScreen())
    in_game = pregame.kind is None and options.kind is None and mat.kind is None
    # The book can't open in battle or the shop, so it's read first and the rest are
    # skipped while it's open: a blank white page looks like the battle's waiting screen,
    # the shop takes a dialog over the book for its own, and the NPC bubble search finds
    # false arrows in its pages.
    book = guard("book", BookScreen(), read_book, w, h, px) if in_game else BookScreen()
    battle = (guard("battle", BattleScreen(), read_screen, w, h, px) if in_game and not book.is_open
              else BattleScreen())
    # The Run? prompt's layout is any OK/Cancel dialog's: outside a battle it's another
    # one (the estate's "Do you want to teleport?"), handled as a stray dialog.
    stray = guard("dialog", None, find_ok_cancel, w, h, px) if battle.kind == "confirm_run" else None
    if stray is None and in_game and battle.kind is None and not book.is_open:
        # A dialog with Cancel alone (a boarding group keeping you in the area): A and B
        # both click it.
        alone = guard("Cancel-only dialog", None, find_cancel_alone, w, h, px)
        stray = (alone, alone) if alone is not None else None
    shop = (guard("gag shop", ShopScreen(), read_shop, w, h, px)
            if in_game and battle.kind is None and not book.is_open else ShopScreen())
    # Walking around: nothing that rules the rest out is showing.
    walking = in_game and battle.kind is None and shop.kind is None and not book.is_open
    # The gags/trunk and tasks HUDs, kept up by toggle_hud. Read before NPCs: the bubble
    # search finds arrows in the trunk's SOS cards, as in the book.
    hud = (guard("HUD", HudScreen(), read_hud, w, h, px, gates.hud_gags, gates.hud_tasks)
           if walking and (gates.hud_gags or gates.hud_tasks) else HudScreen())
    # Gardening, before NPCs too: the bubble search finds one in the bean picker.
    estate = walking and gates.estate
    garden = guard("gardening", GardenScreen(), read_garden, w, h, px) if estate else GardenScreen()
    intro = guard("gardening intro", GardenIntro(), read_garden_intro, w, h, px) if estate else GardenIntro()
    mailbox = guard("mailbox", MailboxScreen(), read_mailbox, w, h, px) if estate else MailboxScreen()
    boarding = guard("boarding group", BoardingScreen(), read_boarding, w, h, px) if walking else BoardingScreen()
    silly = guard("Silly Meter", SillyScreen(), read_silly, w, h, px) if walking else SillyScreen()
    golf = (guard("golf green", GolfGreenScreen(), read_golf_green, w, h, px) if walking and gates.golf
            else GolfGreenScreen())
    fishing = guard("fishing", FishingScreen(), read_fishing, w, h, px) if walking and gates.fish else FishingScreen()
    facility = (guard("facility", FacilityScreen(), read_facility, w, h, px)
                if walking and gates.cog_hq and not golf.is_open else FacilityScreen())
    npc = (guard("NPC", NpcScreen(), read_npc, w, h, px, frame.rgb())
           if (walking and hud.kind != "trunk" and not garden.popup and not mailbox.is_open
               and not golf.is_open and not facility.popup
               # The bubble search took the fishing bucket's "4/20" for a bubble's arrow;
               # nobody talks to NPCs from a dock.
               and fishing.kind is None and not intro.is_open)
           else NpcScreen())
    # Speedchat and the friends list work in battle too.
    menus = in_game and shop.kind is None and npc.kind != "tasks"
    speedchat = (guard("speedchat", SpeedchatScreen(), read_speedchat, w, h, px, gates.look_for_unite)
                 if menus else SpeedchatScreen())
    friends = (guard("friends list", FriendsScreen(), read_friends, w, h, px, gates.friends_dialogs)
               if menus else FriendsScreen())
    pies = bool(in_game and gates.pies and battle.kind is None and not book.is_open
                and guard("pie round", False, read_pie_round, w, h, px))
    # Buttons the overworld reads only when pressed, read here for their hints.
    calm = (gates.hints and walking and npc.kind is None and not speedchat.is_open and friends.kind is None)
    mail = guard("Clarabelle", None, read_mail, w, h, px) if calm else None
    hop = guard("Hop off", None, read_hop_off, w, h, px) if calm else None
    leave = guard("leave button", None, read_leave, w, h, px) if calm and gates.leave else None
    # Walking around and in battle (its badge shows there too).
    friends_button = (not gates.hints or not in_game
                      or guard("friends button", True, ui.is_visible, ui.FRIENDS_BUTTON, w, h, px))
    book_button = not calm or guard("book button", True, ui.is_visible, ui.BOOK_BUTTON, w, h, px)
    return Reads(options=options, mat=mat, pregame=pregame, book=book, battle=battle, stray_dialog=stray,
                 shop=shop, hud=hud, garden=garden, garden_intro=intro, mailbox=mailbox, boarding=boarding,
                 silly=silly, golf=golf, fishing=fishing, facility=facility, npc=npc, speedchat=speedchat,
                 friends=friends, pies=pies,
                 hint_mail_close=mail.close if mail else None, hint_mail_icon=mail.icon if mail else None,
                 hint_hop=hop, hint_leave=leave, hint_friends=friends_button, hint_book=book_button)


def changes(old: Reads, new: Reads) -> list[str]:
    """What changed between two reads, for the debug log."""
    out = []
    if (new.options.kind, new.options.tab) != (old.options.kind, old.options.tab):
        out.append(f"Options: {new.options.kind or 'closed'}"
                   + (f" ({new.options.tab + 1})" if new.options.tab is not None else ""))
    if new.mat.kind != old.mat.kind:
        out.append(f"Make-a-Toon: {new.mat.kind or 'closed'}")
    if new.pregame.kind != old.pregame.kind:
        out.append(f"Pre-game screen: {new.pregame.kind or 'none'}")
    if new.battle.kind != old.battle.kind:
        out.append(f"Battle screen: {new.battle.kind or 'none'}")
    b, ob = new.book, old.book
    if (b.is_open, b.page, b.dialog is not None) != (ob.is_open, ob.page, ob.dialog is not None):
        out.append(f"Book: {'closed' if not b.is_open else 'dialog' if b.dialog else b.page or 'unknown page'}")
    if new.shop.kind != old.shop.kind:
        out.append(f"Gag shop screen: {new.shop.kind or 'none'}")
    if new.hud.kind != old.hud.kind:
        out.append(f"HUD: {new.hud.kind or 'none'}")
    g = new.garden
    if g != old.garden:
        out.append(f"Gardening: {'bean picker' if g.planting else 'sell popup' if g.selling else 'OK popup' if g.ok else 'panel' if g.is_open else 'none'}"
                   + (" (no beans)" if g.planting and not g.beans else ""))
    if new.garden_intro.is_open != old.garden_intro.is_open:
        out.append(f"Gardening intro: {'open' if new.garden_intro.is_open else 'closed'}")
    if new.mailbox != old.mailbox:
        out.append(f"Mailbox: {'open' if new.mailbox.is_open else 'closed'}")
    if new.boarding.kind != old.boarding.kind:
        out.append(f"Boarding group: {new.boarding.kind or 'none'}")
    if new.silly.card != old.silly.card:
        out.append(f"Silly Meter: {'open' if new.silly.card else 'closed'}")
    if new.golf.is_open != old.golf.is_open:
        out.append(f"Golf green: {'up' if new.golf.is_open else 'gone'}")
    if new.fishing.kind != old.fishing.kind:
        out.append(f"Fishing: {new.fishing.kind or 'none'}")
    f, of = new.facility, old.facility
    if (f.popup, len(f.tags)) != (of.popup, len(of.tags)):
        out.append(f"Facility: {len(f.tags)} nametags" + (", popup up" if f.popup else ""))
    if new.npc.kind != old.npc.kind:
        out.append(f"NPC screen: {new.npc.kind or 'none'}")
    if new.speedchat.is_open != old.speedchat.is_open:
        out.append(f"Speedchat menu: {'open' if new.speedchat.is_open else 'closed'}")
    if new.friends.kind != old.friends.kind:
        out.append(f"Friends screen: {new.friends.kind or 'none'}")
    if new.pies != old.pies:
        out.append(f"VP pie round: {'on' if new.pies else 'off'}")
    return out


class ReadWorker:
    """Reads the TTR window on its own thread. request() asks for a read (one at a time:
    a request while one is running waits for it); take() hands back the newest result
    once, with the generation it was asked for under, so the loop can drop a read that
    started before a pause or a window switch."""

    def __init__(self, guard: Guard, snapshot: Callable[[int, bool], Frame]):
        """snapshot(hwnd, background): the window's frame (TTRView.snapshot)."""
        self._guard, self._snapshot = guard, snapshot
        self._cond = threading.Condition()
        self._job: tuple[int, bool, Gates, int] | None = None
        self._running = False
        self._result: tuple[int, Reads] | None = None
        self._stopping = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="screen-reads", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        with self._cond:
            self._stopping = True
            self._cond.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    @property
    def busy(self) -> bool:
        """A read is asked for or running."""
        with self._cond:
            return self._job is not None or self._running

    def request(self, hwnd: int, background: bool, gates: Gates, generation: int) -> None:
        with self._cond:
            self._job = (hwnd, background, gates, generation)
            self._cond.notify_all()

    def take(self) -> tuple[int, Reads] | None:
        with self._cond:
            result, self._result = self._result, None
            return result

    def read_now(self, hwnd: int, background: bool, gates: Gates) -> Reads:
        """One read on the calling thread (tests, tools)."""
        frame = self._guard("window capture", None, self._snapshot, hwnd, background)
        return Reads() if frame is None else read_all(frame, gates, self._guard)

    def _run(self) -> None:
        while True:
            with self._cond:
                self._cond.wait_for(lambda: self._job is not None or self._stopping)
                if self._stopping:
                    return
                hwnd, background, gates, generation = self._job
                self._job, self._running = None, True
            # Guarded as a whole too, so nothing can end the thread.
            reads = self._guard("screen reading", Reads(), self.read_now, hwnd, background, gates)
            with self._cond:
                self._result = (generation, reads)
                self._running = False
