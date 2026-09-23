"""
Per-connection session state machine.

Deliberately decoupled from asyncio/sockets: a Session only needs a
`send_raw(text)` callable and a `close_callback()` callable, so the whole
login -> chargen -> playing flow can be unit-tested with a fake transport
(see test_smoke.py) without opening any real network socket.

Design note: for simplicity in this initial phase, one account maps to
exactly one character (classic early-ROM style). Multiple characters per
account could be added later without changing the storage format much.
"""

import time
from enum import Enum, auto
from typing import Callable, List, Optional

import ascii_art
import canon_names
import colors
import commands
import config
import data_appearance
import data_clans
import data_loadouts
import data_jutsu
import biomes
import data_kekkei_genkai
import leveling
import profanity_filter
import security
import storage
import world
from data_classes import CLASSES, class_names_display, apply_class_stat_bonus
from data_villages import VILLAGES, village_names_display
from models import Account, Player
from prompt import render_prompt

ACTIVE_SESSIONS: List["Session"] = []


class State(Enum):
    NAME = auto()
    LOGIN_PASSWORD = auto()
    NEW_CHAR_PASSWORD = auto()
    NEW_CHAR_PASSWORD_CONFIRM = auto()
    ADMIN_BOOTSTRAP_PASSWORD = auto()
    ADMIN_BOOTSTRAP_CONFIRM = auto()
    CHARGEN_VILLAGE = auto()
    CHARGEN_CLASS = auto()
    CHARGEN_CLAN = auto()
    CHARGEN_LOADOUT = auto()
    CHARGEN_SEX = auto()
    CHARGEN_SKIN_TONE = auto()
    CHARGEN_HAIR_COLOR = auto()
    CHARGEN_EYE_COLOR = auto()
    CHARGEN_BUILD = auto()
    CHARGEN_PERSONALITY = auto()
    CHARGEN_CONFIRM = auto()
    PLAYING = auto()
    EDITING = auto()        # multi-line text editor (e.g. rset desc)
    PENDING_LINE = auto()   # single-line prompt (e.g. rset name)
    PAGING = auto()         # mid-pager, waiting for "continue" (see send_paginated)
    CLOSED = auto()


class _PvpEnemyAdapter:
    """Lets render_prompt's mob-shaped interface (name/health/max_health)
    work for a Player PvP target too, without render_prompt needing to
    know about two different opponent types."""

    def __init__(self, player: Player):
        self.name = player.name
        self.health = player.health
        self.max_health = player.maximum_health


class Session:
    def __init__(self, send_raw: Callable[[str], None], close_callback: Callable[[], None]):
        self.send_raw = send_raw
        self.close_callback = close_callback
        self.state = State.NAME
        self.color_enabled = True

        self.account: Optional[Account] = None
        self.player: Optional[Player] = None

        # Transient (not saved) runtime state
        self.combat_target = None    # combat.Mob currently being fought, if any
        self.pvp_target = None       # another Session currently being fought, if any --
                                      # deliberately separate from combat_target (Mob-only)
                                      # rather than a duck-typed union, so mob combat's
                                      # existing, well-tested internals need zero changes

        # Player grouping (groups.py) -- also transient/session-level,
        # like pvp_target/combat_target above, since a group only makes
        # sense while its members are online.
        self.group = None                    # groups.Group this session belongs to, if any
        self.trade = None                    # trade.Trade this session is currently negotiating, if any
        self.duel = None                     # duel.Duel this session is currently in (proposed or active), if any
        self.pending_cast = None             # combat.PendingCast in progress (hand-sign casting delay), if any
        self.recent_chat_times = []          # timestamps of recent say/ooc/vchat messages, for spam detection (Section 95)
        self.pending_group_invite = None      # groups.Group that invited this session, if any
        self.last_transferred_player_name = None  # Transfer/Return (Section 126): whoever THIS immortal most recently transferred, by name -- bare 'return' always targets this

        # Generic interactive editor state (used by rset desc/name, and
        # reusable later by mset/oset for their own free-text fields).
        self._editor_buffer: List[str] = []
        self._editor_on_save: Optional[Callable[[str], None]] = None
        self._pending_line_callback: Optional[Callable[[str], None]] = None

        # Pager state (see send_paginated/_handle_paging below) -- lines
        # not yet shown, and the state to return to once they are.
        self._pager_remaining: List[str] = []
        self._pager_return_state = State.PLAYING

        # Pending timed action (see start_timed_action below) -- for
        # anything that shouldn't resolve instantly (fishing, mining,
        # chopping, gambling). Server.py's pulse loop checks this every
        # pulse; commands.py starts one instead of resolving
        # immediately. A dict with keys: resolve_at (time.time()
        # target), resolve_fn (called with no args once the delay is
        # up), label (for the "already busy" refusal message), and
        # optionally flavor_schedule (a list of (offset_seconds,
        # message) pairs for intermediate messages during a long wait,
        # e.g. gambling's "the dice clatter...") and flavor_sent (how
        # many of those have already been shown). None when idle.
        self.pending_action: Optional[dict] = None

        # Scratch chargen state
        self._pending_name: Optional[str] = None
        self._pending_password: Optional[str] = None
        self._pending_village: Optional[str] = None
        self._pending_class: Optional[str] = None
        self._pending_clan: str = "none"
        self._pending_loadout: str = "balanced"
        self._pending_sex: str = "male"
        self._pending_skin_tone: str = "tan"
        self._pending_hair_color: str = "black"
        self._pending_eye_color: str = "brown"
        self._pending_build: str = "athletic"
        self._pending_personality: str = "confident"
        self._pending_admin_bootstrap = False

        ACTIVE_SESSIONS.append(self)
        self.send(ascii_art.login_screen())
        self.send("Welcome to the Naruto-Inspired ROM 2.4-style MUD.")
        self.send("By what name shall we call you?")

    # --- Output helpers ---------------------------------------------------

    def send(self, text: str) -> None:
        rendered = colors.render(text, self.color_enabled)
        self.send_raw(rendered + "\r\n")

    def send_prompt(self) -> None:
        if self.state != State.PLAYING or not self.player:
            return
        is_staff = self.account is not None and self.account.staff_level != "player"
        enemy = self.combat_target
        if enemy is None and self.pvp_target is not None and self.pvp_target.player:
            enemy = _PvpEnemyAdapter(self.pvp_target.player)
        p = render_prompt(self.player, mob=enemy, is_staff=is_staff)
        if p:
            self.send_raw("\r\n" + colors.render(p, self.color_enabled) + "\r\n")

    def active_sessions(self) -> List["Session"]:
        return [s for s in ACTIVE_SESSIONS if s.state == State.PLAYING]

    def broadcast_room(self, text: str, exclude_self: bool = False) -> None:
        if not self.player:
            return
        for other in self.active_sessions():
            if exclude_self and other is self:
                continue
            if other.player and other.player.room_vnum == self.player.room_vnum:
                other.send(text)

    def broadcast_all(self, text: str, exclude_self: bool = False) -> None:
        """Server-wide channel (e.g. OOC) -- every connected, playing session."""
        for other in self.active_sessions():
            if exclude_self and other is self:
                continue
            other.send(text)

    def broadcast_village(self, village: str, text: str, exclude_self: bool = False) -> None:
        """Village-scoped channel -- every playing session whose character
        belongs to the given village, regardless of what room they're in."""
        for other in self.active_sessions():
            if exclude_self and other is self:
                continue
            if other.player and other.player.village == village:
                other.send(text)

    def request_close(self) -> None:
        if self.state == State.PLAYING and self.player:
            import commands
            import config
            village_colored = commands.village_name_colored(self.player.village)
            self.broadcast_all(
                f"&[226]***&x  &[51]{self.player.name}&x of {village_colored} "
                f"has left &[45]{config.MUD_NAME}&x!  &[226]***&x",
                exclude_self=True,
            )
        self.state = State.CLOSED
        if self in ACTIVE_SESSIONS:
            ACTIVE_SESSIONS.remove(self)
        if self.group is not None:
            import groups
            groups.remove_member(self.group, self)
            self.group = None
        if self.trade is not None:
            import trade as trade_module
            trade_module.cancel_trade(self.trade)
        if self.duel is not None:
            import duel as duel_module
            if self.duel.accepted:
                # Already underway -- disconnecting would otherwise strand
                # the other player alone in the arena. End it the same way
                # a genuine defeat would, sending both home; no penalty
                # either way, per confirmed design, so which side is
                # nominally the "loser" here doesn't matter.
                duel_module.end_duel(self.duel, self)
            else:
                duel_module.cancel_duel(self.duel)
        self.close_callback()

    # --- Generic interactive editors (used by rset desc/name, etc.) -------

    def enter_editor(self, on_save: Callable[[str], None], initial_text: str = "",
                      header: Optional[str] = None) -> None:
        """Open a ROM-style line editor. Lines are appended until the user
        types '.' or '/s' to save, '/a' to abort, '/c' to clear the buffer,
        '/l' to list it, or '/h' for help. `on_save` receives the final text."""
        self._editor_buffer = initial_text.splitlines() if initial_text else []
        self._editor_on_save = on_save
        self.state = State.EDITING
        self.send(header or "Entering the line editor.")
        if self._editor_buffer:
            self.send("--- current text ---")
            for line in self._editor_buffer:
                self.send(line)
            self.send("--- end ---")
        self.send("Type your text below. '.' or '/s' saves, '/a' aborts, '/c' clears, '/l' lists, '/h' for help.")

    def _handle_editing(self, line: str) -> None:
        stripped = line.strip()

        if stripped in (".", "/s"):
            text = "\n".join(self._editor_buffer)
            callback = self._editor_on_save
            self._editor_buffer = []
            self._editor_on_save = None
            self.state = State.PLAYING
            callback(text)
            self.send_prompt()
            return

        if stripped == "/a":
            self._editor_buffer = []
            self._editor_on_save = None
            self.state = State.PLAYING
            self.send("Edit aborted; no changes made.")
            self.send_prompt()
            return

        if stripped == "/c":
            self._editor_buffer = []
            self.send("Buffer cleared.")
            return

        if stripped == "/l":
            if not self._editor_buffer:
                self.send("(buffer is empty)")
            for i, buffered_line in enumerate(self._editor_buffer, 1):
                self.send(f"{i}: {buffered_line}")
            return

        if stripped == "/h":
            self.send(
                "Editor commands:\n"
                "  .  or /s   save and exit\n"
                "  /a         abort (discard changes)\n"
                "  /c         clear the buffer\n"
                "  /l         list the buffer so far\n"
                "  /h         this help"
            )
            return

        self._editor_buffer.append(line)

    def enter_single_line(self, prompt_text: str, on_submit: Callable[[str], None]) -> None:
        """Ask a single follow-up question (e.g. 'rset name' with no
        arguments) and hand the raw reply to `on_submit`."""
        self.send(prompt_text)
        self._pending_line_callback = on_submit
        self.state = State.PENDING_LINE

    def _handle_pending_line(self, line: str) -> None:
        callback = self._pending_line_callback
        self._pending_line_callback = None
        self.state = State.PLAYING
        callback(line)
        self.send_prompt()

    PAGER_LINES_PER_PAGE = 20

    def send_paginated(self, text: str, lines_per_page: int = PAGER_LINES_PER_PAGE) -> None:
        """Like send(), but for long output: shows `lines_per_page` lines
        at a time, then waits for the player to continue before showing
        more, instead of dumping everything at once. Text with fewer
        lines than that just goes straight through via send() -- no
        pager prompt for output that was never going to scroll past a
        screen anyway.

        The wait-for-continue step is a plain line-buffered read (the
        next thing the player sends, of any content, advances to the
        next page) rather than a true single raw keystroke -- this
        server reads whole lines over telnet, not individual keys, so
        "press any key" isn't literally available; "press enter" is the
        closest equivalent within that constraint."""
        lines = text.split("\n")
        if len(lines) <= lines_per_page:
            self.send(text)
            return
        self._pager_remaining = lines[lines_per_page:]
        self._pager_return_state = self.state
        self.send("\n".join(lines[:lines_per_page]))
        remaining_count = len(self._pager_remaining)
        self.send(f"&D-- more ({remaining_count} more line(s) -- press enter to continue, or 'q' to stop) --&x")
        self.state = State.PAGING

    def _handle_paging(self, line: str) -> None:
        if line.strip().lower() in ("q", "quit", "x"):
            self._pager_remaining = []
            self.state = self._pager_return_state
            self.send("&D(stopped -- rest of the output skipped)&x")
            self.send_prompt()
            return
        lines_per_page = self.PAGER_LINES_PER_PAGE
        page = self._pager_remaining[:lines_per_page]
        self._pager_remaining = self._pager_remaining[lines_per_page:]
        self.send("\n".join(page))
        if self._pager_remaining:
            self.send(f"&D-- more ({len(self._pager_remaining)} more line(s) -- press enter to continue, or 'q' to stop) --&x")
        else:
            self.state = self._pager_return_state
            self.send_prompt()

    def start_timed_action(self, label: str, delay_seconds: float, resolve_fn: Callable[[], None],
                            flavor_schedule: Optional[List[tuple]] = None) -> None:
        """Begins a delayed action -- fishing/mining/chopping/gambling
        shouldn't resolve instantly. `resolve_fn` is called with no
        args once `delay_seconds` have passed (a closure over whatever
        context the caller needs, e.g. which rod/wager was used).
        `flavor_schedule` is an optional list of (offset_seconds,
        message) pairs shown along the way, e.g. gambling's "the dice
        clatter across the table..." partway through a ~1 minute wait.
        Call is_busy() before this to refuse a second action while one
        is already pending, matching every command that uses this."""
        self.pending_action = {
            "resolve_at": time.time() + delay_seconds,
            "resolve_fn": resolve_fn,
            "label": label,
            "flavor_schedule": flavor_schedule or [],
            "flavor_sent": 0,
            "started_at": time.time(),
        }

    def is_busy(self) -> bool:
        return self.pending_action is not None

    def process_pending_action(self) -> None:
        """Called every pulse (server.py) for every PLAYING session.
        Sends any flavor messages whose time has come, then resolves
        the action once its delay is up."""
        action = self.pending_action
        if action is None:
            return
        now = time.time()
        schedule = action["flavor_schedule"]
        while action["flavor_sent"] < len(schedule) and now >= action["started_at"] + schedule[action["flavor_sent"]][0]:
            self.send(schedule[action["flavor_sent"]][1])
            action["flavor_sent"] += 1
        if now >= action["resolve_at"]:
            resolve_fn = action["resolve_fn"]
            self.pending_action = None
            resolve_fn()
            self.send_prompt()

    # --- Main dispatch -----------------------------------------------------

    def handle_line(self, line: str) -> None:
        line = line.strip("\r\n")
        try:
            if self.state == State.NAME:
                self._handle_name(line)
            elif self.state == State.LOGIN_PASSWORD:
                self._handle_login_password(line)
            elif self.state == State.NEW_CHAR_PASSWORD:
                self._handle_new_password(line)
            elif self.state == State.NEW_CHAR_PASSWORD_CONFIRM:
                self._handle_new_password_confirm(line)
            elif self.state == State.ADMIN_BOOTSTRAP_PASSWORD:
                self._handle_admin_bootstrap_password(line)
            elif self.state == State.ADMIN_BOOTSTRAP_CONFIRM:
                self._handle_admin_bootstrap_confirm(line)
            elif self.state == State.CHARGEN_VILLAGE:
                self._handle_chargen_village(line)
            elif self.state == State.CHARGEN_CLASS:
                self._handle_chargen_class(line)
            elif self.state == State.CHARGEN_CLAN:
                self._handle_chargen_clan(line)
            elif self.state == State.CHARGEN_LOADOUT:
                self._handle_chargen_loadout(line)
            elif self.state == State.CHARGEN_SEX:
                self._handle_chargen_sex(line)
            elif self.state == State.CHARGEN_SKIN_TONE:
                self._handle_chargen_skin_tone(line)
            elif self.state == State.CHARGEN_HAIR_COLOR:
                self._handle_chargen_hair_color(line)
            elif self.state == State.CHARGEN_EYE_COLOR:
                self._handle_chargen_eye_color(line)
            elif self.state == State.CHARGEN_BUILD:
                self._handle_chargen_build(line)
            elif self.state == State.CHARGEN_PERSONALITY:
                self._handle_chargen_personality(line)
            elif self.state == State.CHARGEN_CONFIRM:
                self._handle_chargen_confirm(line)
            elif self.state == State.PLAYING:
                self._handle_playing(line)
            elif self.state == State.EDITING:
                self._handle_editing(line)
            elif self.state == State.PENDING_LINE:
                self._handle_pending_line(line)
            elif self.state == State.PAGING:
                self._handle_paging(line)
        except Exception as exc:  # pragma: no cover - safety net
            self.send(f"&RSomething went wrong processing that command ({exc}).&x")

    # --- Login / account bootstrap -----------------------------------------

    def _handle_name(self, line: str) -> None:
        name = line.strip()
        if not name.isalpha() or not (2 <= len(name) <= 20):
            self.send("Names must be 2-20 letters only. What name would you like?")
            return

        self._pending_name = name.lower().capitalize()

        if name.lower() == config.ADMIN_NAME:
            if storage.account_exists(config.ADMIN_NAME):
                self.state = State.LOGIN_PASSWORD
                self.send("Password:")
            else:
                self._pending_admin_bootstrap = True
                self.state = State.ADMIN_BOOTSTRAP_PASSWORD
                self.send(
                    "No Implementor password has been set for this server yet.\n"
                    f"You are creating the primary administrator account '{config.ADMIN_NAME}'.\n"
                    f"Choose a secure password (at least {config.MIN_PASSWORD_LENGTH} characters):"
                )
            return

        if storage.account_exists(self._pending_name):
            self.state = State.LOGIN_PASSWORD
            self.send("Password:")
            return

        if canon_names.is_blocked(self._pending_name):
            self.send(
                f"'{self._pending_name}' is a canon Naruto character -- this world is an "
                "alternate timeline with player-created ninja, not canon characters. "
                "Please choose a different name."
            )
            self._pending_name = None
            return

        if profanity_filter.is_blocked(self._pending_name):
            self.send(f"'{self._pending_name}' isn't an allowed name. Please choose a different name.")
            self._pending_name = None
            return

        self.send(f"'{self._pending_name}' is a new name. Create a new character? [Y/N]")
        self.state = State.NEW_CHAR_PASSWORD_CONFIRM
        # Reuse this state as a simple Y/N gate before asking for a password.
        self._awaiting_new_char_confirmation = True

    def _handle_login_password(self, line: str) -> None:
        account = storage.load_account(self._pending_name)
        if account is None:
            self.send("Something went wrong loading that account. Disconnecting.")
            self.request_close()
            return

        if account.locked_until and time.time() < account.locked_until:
            self.send("This account is temporarily locked due to failed login attempts.")
            self.request_close()
            return

        if not security.verify_password(line, account.salt_hex, account.hash_hex):
            account.failed_attempts += 1
            if account.failed_attempts >= config.MAX_FAILED_LOGINS:
                account.locked_until = time.time() + config.LOCKOUT_SECONDS
                storage.save_account(account)
                self.send("Too many failed attempts. This account is now temporarily locked.")
                self.request_close()
                return
            storage.save_account(account)
            self.send("Wrong password.")
            self.send("Password:")
            return

        account.failed_attempts = 0
        storage.save_account(account)
        self.account = account

        if account.forced_reset:
            self.state = State.ADMIN_BOOTSTRAP_PASSWORD
            self._pending_admin_bootstrap = False
            self.send("You must choose a new password before continuing.")
            self.send(f"Choose a secure password (at least {config.MIN_PASSWORD_LENGTH} characters):")
            return

        player = storage.load_player(self._pending_name)
        if player is None:
            self.send("No character data found for that account. Disconnecting.")
            self.request_close()
            return
        self._enter_world(player)

    # --- New (non-admin) character password -------------------------------

    def _handle_new_password_confirm(self, line: str) -> None:
        answer = line.strip().lower()
        if answer not in ("y", "yes", "n", "no"):
            self.send("Please answer Y or N.")
            return
        if answer in ("n", "no"):
            self.send("Okay. Disconnecting.")
            self.request_close()
            return
        self.state = State.NEW_CHAR_PASSWORD
        self.send(f"Choose a password (at least {config.MIN_PASSWORD_LENGTH} characters):")

    def _handle_new_password(self, line: str) -> None:
        ok, reason = security.validate_new_password(line, self._pending_name)
        if not ok:
            self.send(reason)
            return
        self._pending_password = line
        self.state = State.CHARGEN_VILLAGE
        self._prompt_village_selection()

    # --- Admin (biran) bootstrap / forced reset ----------------------------

    def _handle_admin_bootstrap_password(self, line: str) -> None:
        ok, reason = security.validate_new_password(line, config.ADMIN_NAME)
        if not ok:
            self.send(reason)
            return
        self._pending_password = line
        self.state = State.ADMIN_BOOTSTRAP_CONFIRM
        self.send("Confirm password:")

    def _handle_admin_bootstrap_confirm(self, line: str) -> None:
        if line != self._pending_password:
            self.send("Passwords did not match. Choose a password again:")
            self.state = State.ADMIN_BOOTSTRAP_PASSWORD
            return

        salt_hex, hash_hex = security.hash_password(self._pending_password)

        if self._pending_admin_bootstrap:
            account = Account(
                name=config.ADMIN_NAME, salt_hex=salt_hex, hash_hex=hash_hex,
                staff_level="implementor",
            )
            storage.save_account(account)
            self.account = account
            self.send("Implementor account created.")
            self.state = State.CHARGEN_VILLAGE
            self._pending_name = config.ADMIN_NAME.capitalize()
            self._prompt_village_selection()
        else:
            # Forced password reset for an existing account.
            self.account.salt_hex, self.account.hash_hex = salt_hex, hash_hex
            self.account.forced_reset = False
            storage.save_account(self.account)
            self.send("Password updated.")
            player = storage.load_player(self.account.name)
            self._enter_world(player)

    # --- Character creation: village / class / confirm ---------------------

    def _prompt_village_selection(self) -> None:
        self.send("&YChoose your starting village (this choice is PERMANENT):&x")
        self.send(village_names_display())

    def _handle_chargen_village(self, line: str) -> None:
        village = line.strip().lower()
        if village not in VILLAGES:
            self.send("That is not a valid village. Please choose one of the listed villages.")
            self._prompt_village_selection()
            return
        self._pending_village = village
        self.state = State.CHARGEN_CLASS
        self.send("&YChoose your primary combat class (this choice is PERMANENT):&x")
        self.send(class_names_display())

    def _handle_chargen_class(self, line: str) -> None:
        cls = line.strip().lower()
        if cls not in CLASSES:
            self.send("That is not a valid class. Please choose one of the listed classes.")
            return
        self._pending_class = cls
        self.state = State.CHARGEN_CLAN
        self.send(
            "&YChoose a clan (optional -- type 'none' to skip; this can be changed "
            "later with 'clan join'):&x\n" + data_clans.clan_names_display(self._pending_village)
        )

    def _handle_chargen_clan(self, line: str) -> None:
        key = line.strip().lower()
        village_clans = data_clans.clans_for_village(self._pending_village)
        if key not in ("none", "") and key not in village_clans:
            self.send(
                "That is not a clan of your village. Type 'none' to skip, or choose one:\n"
                + data_clans.clan_names_display(self._pending_village)
            )
            return
        self._pending_clan = key if key in village_clans else "none"
        self.state = State.CHARGEN_LOADOUT
        self.send(
            "&YChoose your starting loadout (this can't be changed later):&x\n"
            + data_loadouts.display_menu()
        )

    def _handle_chargen_loadout(self, line: str) -> None:
        key = line.strip().lower()
        if key not in data_loadouts.LOADOUTS:
            self.send(
                "That is not a valid loadout. Please choose one:\n"
                + data_loadouts.display_menu()
            )
            return
        self._pending_loadout = key
        self.state = State.CHARGEN_SEX
        self.send("&YChoose your character's sex:&x\n" + data_appearance.sex_menu())

    def _handle_chargen_sex(self, line: str) -> None:
        key = line.strip().lower()
        if key not in data_appearance.SEX_OPTIONS:
            self.send(
                "That is not a valid choice. Please choose one:\n" + data_appearance.sex_menu()
            )
            return
        self._pending_sex = key
        self.state = State.CHARGEN_SKIN_TONE
        self.send(
            "Choose your character's skin tone (enter a number):\n"
            + data_appearance.skin_tone_menu()
        )

    def _handle_chargen_skin_tone(self, line: str) -> None:
        choice = line.strip()
        if choice.isdigit() and 1 <= int(choice) <= len(data_appearance.SKIN_TONES):
            tone = data_appearance.SKIN_TONES[int(choice) - 1]
        elif choice.lower() in data_appearance.SKIN_TONES:
            tone = choice.lower()
        else:
            self.send(
                "That is not a valid choice. Please choose one:\n"
                + data_appearance.skin_tone_menu()
            )
            return
        self._pending_skin_tone = tone
        self.state = State.CHARGEN_HAIR_COLOR
        self.send(
            "&YChoose your character's hair color (enter a number):&x\n"
            + data_appearance.hair_color_menu()
        )

    def _handle_chargen_hair_color(self, line: str) -> None:
        choice = line.strip()
        if choice.isdigit() and 1 <= int(choice) <= len(data_appearance.HAIR_COLORS):
            color = data_appearance.HAIR_COLORS[int(choice) - 1]
        elif choice.lower() in data_appearance.HAIR_COLORS:
            color = choice.lower()
        else:
            self.send(
                "That is not a valid choice. Please choose one:\n"
                + data_appearance.hair_color_menu()
            )
            return
        self._pending_hair_color = color
        self.state = State.CHARGEN_EYE_COLOR
        self.send(
            "&YChoose your character's eye color (enter a number):&x\n"
            + data_appearance.eye_color_menu()
        )

    def _handle_chargen_eye_color(self, line: str) -> None:
        choice = line.strip()
        if choice.isdigit() and 1 <= int(choice) <= len(data_appearance.EYE_COLORS):
            color = data_appearance.EYE_COLORS[int(choice) - 1]
        elif choice.lower() in data_appearance.EYE_COLORS:
            color = choice.lower()
        else:
            self.send(
                "That is not a valid choice. Please choose one:\n"
                + data_appearance.eye_color_menu()
            )
            return
        self._pending_eye_color = color
        self.state = State.CHARGEN_BUILD
        self.send(
            "&YChoose your character's build (enter a number):&x\n"
            + data_appearance.build_menu()
        )

    def _handle_chargen_build(self, line: str) -> None:
        choice = line.strip()
        if choice.isdigit() and 1 <= int(choice) <= len(data_appearance.BUILDS):
            build = data_appearance.BUILDS[int(choice) - 1]
        elif choice.lower() in data_appearance.BUILDS:
            build = choice.lower()
        else:
            self.send(
                "That is not a valid choice. Please choose one:\n"
                + data_appearance.build_menu()
            )
            return
        self._pending_build = build
        self.state = State.CHARGEN_PERSONALITY
        self.send(
            "&YChoose your character's personality trait (enter a number):&x\n"
            + data_appearance.personality_trait_menu()
        )

    def _handle_chargen_personality(self, line: str) -> None:
        choice = line.strip()
        if choice.isdigit() and 1 <= int(choice) <= len(data_appearance.PERSONALITY_TRAITS):
            trait = data_appearance.PERSONALITY_TRAITS[int(choice) - 1]
        elif choice.lower() in data_appearance.PERSONALITY_TRAITS:
            trait = choice.lower()
        else:
            self.send(
                "That is not a valid choice. Please choose one:\n"
                + data_appearance.personality_trait_menu()
            )
            return
        self._pending_personality = trait
        self.state = State.CHARGEN_CONFIRM
        village_name = VILLAGES[self._pending_village]["village_name"]
        class_name = CLASSES[self._pending_class]["display_name"]
        clan_name = data_clans.display_name(self._pending_clan)
        loadout_name = data_loadouts.LOADOUTS[self._pending_loadout]["display_name"]
        sex_name = data_appearance.sex_display(self._pending_sex)
        tone_name = data_appearance.skin_tone_display(self._pending_skin_tone)
        hair_name = data_appearance.hair_color_display(self._pending_hair_color)
        eye_name = data_appearance.eye_color_display(self._pending_eye_color)
        build_name = data_appearance.build_display(self._pending_build)
        personality_name = data_appearance.personality_trait_display(self._pending_personality)
        self.send(
            "Your village and primary combat class are permanent. Your clan can be "
            "changed later with 'clan join'. Your loadout, sex, skin tone, hair color, "
            "eye color, build, and personality trait cannot be changed later.\n\n"
            f"Village: {village_name}\n"
            f"Class: {class_name}\n"
            f"Clan: {clan_name}\n"
            f"Loadout: {loadout_name}\n"
            f"Sex: {sex_name}\n"
            f"Skin Tone: {tone_name}\n"
            f"Hair Color: {hair_name}\n"
            f"Eye Color: {eye_name}\n"
            f"Build: {build_name}\n"
            f"Personality: {personality_name}\n\n"
            "Create this character? [Y/N]"
        )

    def _handle_chargen_confirm(self, line: str) -> None:
        answer = line.strip().lower()
        if answer not in ("y", "yes", "n", "no"):
            self.send("Please answer Y or N.")
            return
        if answer in ("n", "no"):
            self.send("Let's choose again.")
            self.state = State.CHARGEN_VILLAGE
            self._prompt_village_selection()
            return

        # Save account (unless this is the admin path, already saved).
        if self.account is None:
            salt_hex, hash_hex = security.hash_password(self._pending_password)
            self.account = Account(name=self._pending_name, salt_hex=salt_hex, hash_hex=hash_hex)
            storage.save_account(self.account)

        player = self._create_player(self._pending_name, self.account.name,
                                      self._pending_village, self._pending_class, self._pending_clan,
                                      self._pending_loadout, self._pending_sex, self._pending_skin_tone,
                                      self._pending_hair_color, self._pending_eye_color,
                                      self._pending_build, self._pending_personality)
        storage.save_player(player)
        self.send(
            f"\nWelcome, {player.name} of {VILLAGES[player.village]['village_name']}!\n"
            "You awaken in your village's Kage Chamber, a new academy student."
        )
        self._enter_world(player)

    @staticmethod
    def _create_player(name: str, account_name: str, village: str, primary_class: str,
                        clan: str = "none", loadout_key: str = "balanced",
                        sex: str = "male", skin_tone: str = "tan",
                        hair_color: str = "black", eye_color: str = "brown",
                        build: str = "athletic", personality_trait: str = "confident") -> Player:
        player = Player(name=name, account_name=account_name)
        player.village = village
        player.village_rank = "academy student"
        player.primary_class = primary_class
        apply_class_stat_bonus(player)
        player.clan = clan
        player.sex = sex
        player.skin_tone = skin_tone
        player.hair_color = hair_color
        player.eye_color = eye_color
        player.build = build
        player.personality_trait = personality_trait
        player.ryo = config.STARTING_RYO
        player.health = player.maximum_health = config.STARTING_HEALTH
        player.chakra = player.maximum_chakra = config.STARTING_CHAKRA
        player.stamina = player.maximum_stamina = config.STARTING_STAMINA
        player.training_points = config.STARTING_TRAINING_POINTS
        player.practice_points = config.STARTING_PRACTICE_POINTS

        headband = f"A {VILLAGES[village]['village_short_name']} Headband"
        loadout = data_loadouts.LOADOUTS.get(loadout_key, data_loadouts.LOADOUTS["balanced"])
        player.equipment = dict(loadout["equipment"])
        player.equipment["head"] = headband
        player.inventory = list(loadout["inventory"])
        for equipped_item in player.equipment.values():
            commands._apply_equipment_stat_bonuses(player, equipped_item, sign=1)

        # Every player starts with the same kit regardless of primary
        # class: one active jutsu per combat category (Ninjutsu/Taijutsu/
        # Genjutsu/Bukijutsu), plus the universal passive. Primary class
        # no longer determines starting skills -- it's still permanent
        # (Section 3) and still governs which jutsu category is used via
        # bare name vs 'perform', but everyone knows all four jutsu.
        player.learned_skills = list(data_jutsu.UNIVERSAL_STARTING_SKILLS)
        player.skill_proficiencies = {skill: 0 for skill in player.learned_skills}

        import content
        player.room_vnum = content._VILLAGE_ROOMS[village]["kage"]
        player.prompt_string = config.DEFAULT_PROMPT

        # Kekkei Genkai: a secret, one-time roll -- see
        # data_kekkei_genkai.py's own docstring for the full design.
        # Nothing about this is ever shown to the player; only a
        # future Level 50 awakening quest (not built yet) can reveal it.
        bloodline_roll = data_kekkei_genkai.roll_inheritance(clan)
        player.bloodline_id = bloodline_roll["bloodline_id"]
        player.bloodline_potential = bloodline_roll["potential"]
        player.bloodline_talent = bloodline_roll["talent"]

        # Chakra nature (Section 79, per direct request) -- a secret,
        # one-time roll, exactly like the Kekkei Genkai roll just
        # above. Nothing about this is shown to the player until they
        # use a Chakra Paper (see commands.py).
        player.chakra_nature = biomes.roll_chakra_nature()

        return player

    # --- Entering the world / normal play -----------------------------------

    def _enter_world(self, player: Player) -> None:
        # Kick any stale/ghost session already playing as this same
        # character. Covers a genuinely abrupt "linkdead" disconnect --
        # no clean TCP close means the old session's connection loop
        # never notices it died (readline() just hangs), so it's never
        # removed from ACTIVE_SESSIONS on its own. Without this check,
        # reconnecting just adds a SECOND session for the same player,
        # which is exactly why they'd show up twice on 'who'.
        for other in list(ACTIVE_SESSIONS):
            if other is not self and other.player and other.player.name.lower() == player.name.lower():
                other.send("\n&RYour connection has been taken over by a new login.&x")
                other.request_close()

        self.player = player
        self.state = State.PLAYING
        self.color_enabled = player.color_enabled

        # Staff jutsu bypass (Section 83, per direct request: "make
        # it so staff get every skill and jutsu regardless of primary
        # class") -- confirmed design: immediate and level-independent,
        # not gated by the character's own level at all. Weapon
        # skills and passives (Strong Fist Style) are NOT class-gated
        # in the first place -- confirmed directly before concluding
        # jutsu was the only actual restriction needing a bypass here.
        if self.account and self.account.staff_level != "player":
            for key in data_jutsu.all_jutsu_keys():
                display = data_jutsu.JUTSU[key]["display_name"]
                if display not in player.learned_skills:
                    player.learned_skills.append(display)
                    player.skill_proficiencies[display] = 0

        # Re-point the storage room's ground_items at THIS player
        # object's own storage_room_items list, not whatever temporary
        # Player instance startup reconciliation used to build the
        # room in the first place -- see world.reconcile_apartment_ownership
        # and apartments.py for the full reasoning. Without this, a
        # live drop/get in the storage room would mutate a list object
        # that's no longer the one this session's own save actually
        # persists.
        if "storage" in player.apartment_expansions and player.apartment_room_vnum is not None:
            import apartments
            storage_vnum = apartments.expansion_room_vnum(player.apartment_room_vnum, "storage")
            storage_room = world.WORLD.get(storage_vnum)
            if storage_room is not None:
                storage_room.ground_items = player.storage_room_items

        # A saved room_vnum can point to a room that no longer exists --
        # most commonly a builder-created room ('rset create') that was
        # never persisted to disk (OLC changes are in-memory only), so
        # it vanishes the moment the server restarts even though a
        # player's own save file still remembers standing in it. Every
        # room-dependent command (look, move, etc.) assumes
        # world.WORLD.get(player.room_vnum) is never None, so left
        # unchecked this crashes the very first thing the player does
        # (often 'look', which also fires automatically right below).
        # Resetting to the player's own village starting room is a
        # safe, always-valid fallback -- it's static content.py-seeded
        # content, never something a builder could have removed.
        if world.WORLD.get(player.room_vnum) is None:
            from data_villages import VILLAGES
            player.room_vnum = VILLAGES[player.village]["starting_room_vnum"]
            self.send(
                "&Y(The room you were last in no longer exists -- you've been "
                "returned to your village.)&x"
            )

        self.send(f"\n&GYou are now playing {player.name}.&x")
        from data_villages import VILLAGES as _VILLAGES
        village_name = _VILLAGES[player.village]["village_name"]
        village_colored = commands.village_name_colored(player.village)
        self.broadcast_all(
            f"&[226]***&x  &[51]{player.name}&x of {village_colored} "
            f"has joined &[45]{config.MUD_NAME}&x!  &[226]***&x",
            exclude_self=True,
        )
        # Per direct confirmation (Section 143): a genuine, safe
        # fallback for any existing character whose own saved
        # room_vnum points at a room that no longer exists (e.g. one
        # of the many rooms wiped when every village was collapsed
        # down to a single room) -- moved to their own village's real,
        # current starting room instead of left stranded.
        if world.WORLD.get(player.room_vnum) is None:
            player.room_vnum = _VILLAGES[player.village]["starting_room_vnum"]
        for line in leveling.sync_universal_skills(player):
            self.send(line)
        commands.cmd_look(self, [])
        self.send_prompt()

    def _handle_playing(self, line: str) -> None:
        line = line.strip()
        if not line:
            self.send_prompt()
            return
        commands.dispatch_line(self, line)
        # Keep color_enabled and player's saved prompt in sync.
        self.player.color_enabled = self.color_enabled
        self.send_prompt()
