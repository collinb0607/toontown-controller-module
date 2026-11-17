"""Which screen owns the controller, from what the readers saw (pipeline.Reads): no
pixels and no mappers, so every overlap can be tested.

Screens stack. TTR's Options window is over everything and Make-a-Toon over the rest.
Battles and the gag shop keep their screen for a moment after their panel goes (a dialog
fading in). Speedchat and the friends list open over battles, conversations and the book,
which pause under them. Walking around ("free"), a few small screens can show at once
(gardening, a facility popup, the mailbox, a stray dialog, the HUD, the gardening
introduction, the Silly Meter, the boarding group): `share` gives each the buttons it
claims that no screen before it took, so two never act on one press.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from .pipeline import Reads


@dataclass(frozen=True)
class Route:
    options: bool = False  # TTR's Options window
    mat: bool = False  # Make-a-Toon
    pregame: bool = False  # the start-up screen or toon selection
    battle: bool = False
    shop: bool = False  # the gag shop (and the trolley's gag picker)
    npc_open: bool = False  # an NPC conversation or task panel is up (it may be paused under a menu)
    npc: bool = False  # ...and has the controller
    speedchat: bool = False
    friends: bool = False  # the friends list or a toon's panel
    book: bool = False  # the shticker book has the controller
    golf: bool = False  # the Cog Golf green: the left stick aims
    fishing: bool = False  # a pond's dock: A casts
    walk: bool = True  # the left stick walks
    free: bool = True  # walking around with nothing else open
    holder: str | None = None  # the menu that may hold the mouse button down
    mode: str = "free"  # which screen's hints show

    @property
    def menu(self) -> bool:
        """Speedchat, the friends list or the book has the controller."""
        return self.speedchat or self.friends or self.book


def route(r: Reads, battle_recent: bool, shop_recent: bool) -> Route:
    """battle_recent / shop_recent: a battle or gag shop screen showed within the grace
    period (app.BATTLE_GRACE_SECONDS)."""
    options = r.options.kind is not None
    mat = r.mat.kind is not None and not options
    pregame = r.pregame.kind is not None
    battle = not options and battle_recent
    shop = not (options or battle) and shop_recent
    # NPC screens come and go with the conversation, so no grace period.
    npc_open = not (battle or shop) and r.npc.kind is not None
    # Speedchat first when both are open: it closes as soon as a phrase is said.
    speedchat = not shop and r.speedchat.is_open
    friends = not (shop or speedchat) and r.friends.kind is not None
    npc = npc_open and not (speedchat or friends)
    # The book is under both (speedchat and the friends list open over it).
    book = not (battle or shop or npc_open or speedchat or friends) and r.book.is_open
    covered = options or mat or pregame or battle or shop or speedchat or friends or r.book.is_open
    golf = r.golf.is_open and not covered
    # Fishing's popups (bucket full, out of jellybeans) are stray dialogs with one button.
    fishing = r.fishing.kind is not None and r.stray_dialog is None and not covered
    # Walking still works mid-conversation (it walks away); not while choosing a task.
    walk = not (options or mat or battle or shop or book or r.npc.kind == "tasks"
                or (pregame and r.pregame.kind != "startup") or golf or fishing)
    free = not (options or mat or pregame or battle or shop or r.npc.kind is not None or speedchat
                or friends or r.book.is_open)
    holder = ("options" if options else "makeatoon" if mat else "book" if book
              else "friends" if friends else "fishing" if fishing else None)
    mode = ("options" if options else "mat" if mat else "pregame" if pregame
            else "speedchat" if speedchat else "friends" if friends else "battle" if battle
            else "shop" if shop else "npc" if npc else "book" if book
            else "golf" if golf else "fishing" if fishing else "free")
    return Route(options=options, mat=mat, pregame=pregame, battle=battle, shop=shop, npc_open=npc_open, npc=npc,
                 speedchat=speedchat, friends=friends, book=book, golf=golf, fishing=fishing, walk=walk,
                 free=free, holder=holder, mode=mode)


# Walking around, the small screens that can show together, in the order they get the
# buttons they claim. A dialog is first: TTR's dialogs are modal, so whatever is behind
# one can't be used anyway.
FREE_ORDER = ("dialog", "garden", "facility", "mailbox", "hud", "garden_intro", "silly", "boarding")


def share(claims: Iterable[tuple[str, frozenset[str]]]) -> dict[str, frozenset[str]]:
    """claims: (screen, the buttons it wants) in FREE_ORDER, for the screens showing.
    Returns each screen's buttons: what it wants, less what a screen before it took."""
    taken: set[str] = set()
    out = {}
    for name, wanted in claims:
        mine = frozenset(wanted) - taken
        taken |= mine
        out[name] = mine
    return out
