"""
Persistence layer.

Uses one JSON file per account and per player under data/. This is a
deliberate departure from classic ROM flat-file player files: JSON is
diff-friendly, easy to migrate (just add a field with a default), and
hard to silently corrupt compared to fixed-order flat fields (see
engineering notes: Phase 0 recommendation to move off brittle flat-file
saves before the field list in Section 45 grows further).
"""

import json
import os
from typing import List, Optional

from models import Account, Player

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
ACCOUNTS_DIR = os.path.join(DATA_DIR, "accounts")
PLAYERS_DIR = os.path.join(DATA_DIR, "players")


def ensure_dirs():
    os.makedirs(ACCOUNTS_DIR, exist_ok=True)
    os.makedirs(PLAYERS_DIR, exist_ok=True)
    os.makedirs(_bug_reports_dir(), exist_ok=True)
    os.makedirs(_ideas_dir(), exist_ok=True)


def _bug_reports_dir() -> str:
    """Computed fresh each call (not cached at import time), same
    reasoning as _jackpots_path() below -- so test_smoke.py reassigning
    storage.DATA_DIR for test isolation is respected."""
    return os.path.join(DATA_DIR, "bug_reports")


def _bug_report_log_path() -> str:
    return os.path.join(_bug_reports_dir(), "reports.txt")


def append_bug_report(player_name: str, village: str, room_vnum: int, message: str) -> None:
    """Appends one player-submitted bug report to a single running,
    plain-text log file (data/bug_reports/reports.txt) -- deliberately
    plain text, not JSON, per explicit request to be able to just open
    and read it directly. Never overwrites; only ever adds a new line
    at the end, so nothing already filed is ever lost."""
    import datetime

    ensure_dirs()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {player_name} ({village}, room {room_vnum}): {message}\n"
    with open(_bug_report_log_path(), "a", encoding="utf-8") as f:
        f.write(entry)


def _ideas_dir() -> str:
    """Computed fresh each call (not cached at import time), same
    reasoning as _jackpots_path() below -- so test_smoke.py reassigning
    storage.DATA_DIR for test isolation is respected."""
    return os.path.join(DATA_DIR, "ideas")


def _idea_log_path() -> str:
    return os.path.join(_ideas_dir(), "ideas.txt")


def append_idea(player_name: str, village: str, room_vnum: int, message: str) -> None:
    """Appends one player-submitted idea to a single running, plain-
    text log file (data/ideas/ideas.txt), per direct request ("like
    the buigs command create a copy of it just make it ideas command
    so players can submit ideas") -- mirrors append_bug_report
    exactly, including the deliberate choice of plain text over JSON
    so staff can just open and read it directly, but kept as a
    genuinely SEPARATE log/directory from bug reports, since the two
    are conceptually distinct. Never overwrites; only ever adds a new
    line at the end, so nothing already filed is ever lost."""
    import datetime

    ensure_dirs()
    os.makedirs(_ideas_dir(), exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {player_name} ({village}, room {room_vnum}): {message}\n"
    with open(_idea_log_path(), "a", encoding="utf-8") as f:
        f.write(entry)


def _jackpots_path() -> str:
    """Computed fresh on each call (not cached at import time) so that
    reassigning storage.DATA_DIR later -- as test_smoke.py does for
    test isolation -- is respected, the same way ACCOUNTS_DIR/
    PLAYERS_DIR already work by being read fresh each call rather than
    baked into a stale module-level path."""
    return os.path.join(DATA_DIR, "jackpots.json")


def load_jackpots() -> dict:
    """The slot machine jackpot pools (slots.py) -- a global value
    shared across every player, unlike everything else in this file
    which is per-account/per-player. Keys are tier costs (as strings,
    since JSON object keys are always strings); values are the
    currently accumulated ryo for that tier's jackpot. Missing file =
    no jackpots seeded yet."""
    path = _jackpots_path()
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_jackpots(jackpots: dict) -> None:
    ensure_dirs()
    with open(_jackpots_path(), "w", encoding="utf-8") as f:
        json.dump(jackpots, f, indent=2)


def _bounties_path() -> str:
    """Same fresh-path-per-call reasoning as _jackpots_path() -- so
    test-time reassignment of storage.DATA_DIR is respected."""
    return os.path.join(DATA_DIR, "bounties.json")


def load_bounties() -> dict:
    """The Bingo Book bounty registry (bounties.py) -- a global value
    shared across every player, unlike everything else in this file.
    Keys are bounty IDs (as strings, since JSON object keys always
    are); missing file = no bounties posted yet."""
    path = _bounties_path()
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_bounties(bounties: dict) -> None:
    ensure_dirs()
    with open(_bounties_path(), "w", encoding="utf-8") as f:
        json.dump(bounties, f, indent=2)


def _territory_path() -> str:
    """Same fresh-path-per-call reasoning as _jackpots_path() -- so
    test-time reassignment of storage.DATA_DIR is respected."""
    return os.path.join(DATA_DIR, "territory.json")


def load_territory() -> dict:
    """The war/territory system's full state (territory.py) -- a
    global value shared across every player, same shape as bounties:
    village treasuries, each control point's owner/garrison, and the
    war window schedule, all as one blob. Missing file = a fresh game
    with no treasury built up yet and every point unclaimed."""
    path = _territory_path()
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_territory(state: dict) -> None:
    ensure_dirs()
    with open(_territory_path(), "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _spawn_points_path() -> str:
    """Same fresh-path-per-call reasoning as _jackpots_path() -- so
    test-time reassignment of storage.DATA_DIR is respected."""
    return os.path.join(DATA_DIR, "spawn_points.json")


def load_spawn_points() -> dict:
    """Staff-assigned persistent spawn points (spawn_points.py) -- a
    global registry of mob/item prototypes that should always exist
    in a given room, re-applied fresh on every server start. Missing
    file = a fresh game with no staff-assigned spawn points yet
    (content.py's own hardcoded static placement is unaffected either
    way -- this is purely additional, builder-configured content)."""
    path = _spawn_points_path()
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_spawn_points(state: dict) -> None:
    ensure_dirs()
    with open(_spawn_points_path(), "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _custom_templates_path() -> str:
    """Same fresh-path-per-call reasoning as _jackpots_path() -- so
    test-time reassignment of storage.DATA_DIR is respected."""
    return os.path.join(DATA_DIR, "templates.json")


def load_custom_templates() -> dict:
    """Custom mob/item prototypes referenced by a spawn point
    (spawn_points.py), per direct request/confirmation ("make sure
    setspawn saves during save world so the spawnpoints dont disapear
    on reboot" -> confirmed the real root cause: a custom mob's own
    template, from 'mset create', was never persisted at all except
    by the separate, MANUAL 'save world' command -- so a spawn point
    pointing at one would survive a restart, but the template it
    needed to actually spawn from wouldn't, silently leaving nothing
    to spawn -> confirmed spawnpoint/setspawn should guarantee this
    automatically, with no separate save world step required).

    Deliberately separate from world_state.json (storage.
    load_world_state/save_world_state) -- that one stays exactly
    what it already was: a full, deliberate, MANUAL "save everything
    live right now" snapshot triggered only by 'save world'. This
    file instead holds only the specific templates a spawn point
    actually depends on, written automatically the moment
    spawn_points.add_spawn_point registers one that isn't already a
    real, built-in content.py template -- no staff command needed at
    all for a spawn point's own mob/item to survive a restart.

    Returns {"mobs": {vnum_str: template_dict}, "items": {vnum_str:
    template_dict}}. Missing file = no spawn point has ever needed a
    custom template saved this way yet."""
    path = _custom_templates_path()
    if not os.path.isfile(path):
        return {"mobs": {}, "items": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_custom_templates(state: dict) -> None:
    ensure_dirs()
    with open(_custom_templates_path(), "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _teams_path() -> str:
    """Same fresh-path-per-call reasoning as _jackpots_path() -- so
    test-time reassignment of storage.DATA_DIR is respected."""
    return os.path.join(DATA_DIR, "teams.json")


def load_teams() -> dict:
    """Every persistent Team (teams.py) -- a genuinely separate system
    from the session-only groups.py, since a team's roster exists
    whether or not its members are currently online (confirmed
    design). Missing file = no teams have ever been created yet."""
    path = _teams_path()
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_teams(state: dict) -> None:
    ensure_dirs()
    with open(_teams_path(), "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _chatlog_path() -> str:
    """Same fresh-path-per-call reasoning as _jackpots_path() -- so
    test-time reassignment of storage.DATA_DIR is respected."""
    return os.path.join(DATA_DIR, "chatlog.json")


def load_chatlog() -> list:
    """The last 25 OOC messages (chatlog.py), per direct request ("add
    a command in game that shows the last 25 ooc chats by typing
    chatlog"). Confirmed persisted to disk -- survives a server
    restart, matching teams.json's own established pattern. Missing
    file = nobody has said anything OOC yet. Each entry is a plain
    dict {"speaker": str, "message": str} -- no timestamp requested,
    kept minimal."""
    path = _chatlog_path()
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_chatlog(entries: list) -> None:
    ensure_dirs()
    with open(_chatlog_path(), "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


def _world_state_path() -> str:
    """Same fresh-path-per-call reasoning as _jackpots_path() -- so
    test-time reassignment of storage.DATA_DIR is respected."""
    return os.path.join(DATA_DIR, "world_state.json")


def load_world_state() -> dict:
    """The full saved world snapshot (rooms/mobs/items), written by
    'save world' -- see world_persistence.py. Missing file = nothing
    has ever been saved yet, so the world is exactly whatever
    content.py builds on its own, unmodified. Loaded and applied on
    TOP of content.py's own population, last, so anything saved here
    always wins over what the code would otherwise build -- confirmed
    design ("Full snapshot...the saved snapshot always wins over what
    content.py would normally build")."""
    path = _world_state_path()
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_world_state(state: dict) -> None:
    ensure_dirs()
    with open(_world_state_path(), "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)



def _tips_path() -> str:
    """Same fresh-path-per-call reasoning as _jackpots_path() -- so
    test-time reassignment of storage.DATA_DIR is respected."""
    return os.path.join(DATA_DIR, "tips.json")


def load_tips() -> list:
    """Staff-curated tip-of-the-day text list (tips.py) -- shown to
    players with their own 'tips' config on, every TIPS_INTERVAL_
    SECONDS (server.py). Missing file = a fresh game with no tips
    added yet."""
    path = _tips_path()
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tips(tips: list) -> None:
    ensure_dirs()
    with open(_tips_path(), "w", encoding="utf-8") as f:
        json.dump(tips, f, indent=2)


def _auctions_path() -> str:
    """Same fresh-path-per-call reasoning as _jackpots_path() -- so
    test-time reassignment of storage.DATA_DIR is respected."""
    return os.path.join(DATA_DIR, "auctions.json")


def load_auctions() -> dict:
    """The Auction House's active listings (auction.py) -- a global
    value shared across every player, unlike everything else in this
    file. Keys are auction IDs (as strings, since JSON object keys
    always are); missing file = no listings posted yet."""
    path = _auctions_path()
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_auctions(auctions: dict) -> None:
    ensure_dirs()
    with open(_auctions_path(), "w", encoding="utf-8") as f:
        json.dump(auctions, f, indent=2)


def _areas_path() -> str:
    """Same fresh-path-per-call reasoning as _jackpots_path()."""
    return os.path.join(DATA_DIR, "areas.json")


def load_areas() -> dict:
    """The area vnum-reservation registry (areas.py) -- a global value
    shared across every builder, unlike everything else in this file.
    Keys are area names (lowercased); missing file = nothing reserved
    yet (content.py's own populate() registers the pre-existing
    "legacy" reservation the first time it runs)."""
    path = _areas_path()
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_areas(areas: dict) -> None:
    ensure_dirs()
    with open(_areas_path(), "w", encoding="utf-8") as f:
        json.dump(areas, f, indent=2)


def _safe_key(name: str) -> str:
    return name.strip().lower()


# --- Accounts -------------------------------------------------------------

def account_path(name: str) -> str:
    return os.path.join(ACCOUNTS_DIR, f"{_safe_key(name)}.json")


def account_exists(name: str) -> bool:
    return os.path.isfile(account_path(name))


def save_account(account: Account) -> None:
    ensure_dirs()
    with open(account_path(account.name), "w", encoding="utf-8") as f:
        json.dump(account.to_dict(), f, indent=2)


def load_account(name: str) -> Optional[Account]:
    path = account_path(name)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return Account.from_dict(json.load(f))


# --- Players ----------------------------------------------------------

def player_path(name: str) -> str:
    return os.path.join(PLAYERS_DIR, f"{_safe_key(name)}.json")


def player_exists(name: str) -> bool:
    return os.path.isfile(player_path(name))


def save_player(player: Player) -> None:
    ensure_dirs()
    with open(player_path(player.name), "w", encoding="utf-8") as f:
        json.dump(player.to_dict(), f, indent=2)


# Legacy (pre-color) prompt presets, mapped to their current colored
# equivalents. Player.prompt_string is saved verbatim at creation time,
# so a character made before color was added to the defaults would
# otherwise be stuck showing the old plain text forever -- this is a
# one-time migration applied on load, not a live import of prompt.py
# (which would create storage -> prompt -> leveling -> storage cycle).
_LEGACY_PROMPT_MIGRATIONS = {
    "<HP:%h/%H CH:%c/%C ST:%s/%S XP:%x/%X Ryo:%r>":
        "&RHP:%h/%H &BCH:%c/%C &GST:%s/%S &CXP:%x/%X &YRyo:%r&x",
    "<HP:%h/%H CH:%c/%C ST:%s/%S>":
        "&RHP:%h/%H &BCH:%c/%C &GST:%s/%S&x",
    "<HP:%h/%H CH:%c/%C ST:%s/%S Enemy:%e%%>":
        "&RHP:%h/%H &BCH:%c/%C &GST:%s/%S &WEnemy:%e%%&x",
    "[%v %k Lvl:%l] HP:%h/%H CH:%c/%C ST:%s/%S XP:%x/%X Ryo:%r MP:%m":
        "&C[%v %k Lvl:%l]&x &RHP:%h/%H &BCH:%c/%C &GST:%s/%S &CXP:%x/%X &YRyo:%r &MMP:%m&x",
    "<%hH %cC %sS>":
        "&R%hH &B%cC &G%sS&x",
}

# skill_proficiencies used to store a level-name string ("untrained" ...
# "mastered"); it's now a raw 0-100 percentage so practice gains can
# scale with Intelligence. Migrate old string values transparently.
_LEGACY_PROFICIENCY_TO_PERCENT = {
    "untrained": 0, "novice": 20, "familiar": 40,
    "skilled": 60, "expert": 80, "mastered": 100,
}


def load_player(name: str) -> Optional[Player]:
    path = player_path(name)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    legacy_experience_curve = "experience_curve_version" not in raw
    player = Player.from_dict(raw)
    if player.prompt_string in _LEGACY_PROMPT_MIGRATIONS:
        player.prompt_string = _LEGACY_PROMPT_MIGRATIONS[player.prompt_string]
    for skill, value in list(player.skill_proficiencies.items()):
        if isinstance(value, str):
            player.skill_proficiencies[skill] = _LEGACY_PROFICIENCY_TO_PERCENT.get(value, 0)
    if legacy_experience_curve:
        player.experience_curve_version = 1
    import leveling
    if leveling.migrate_experience_curve(player):
        save_player(player)
    return player


def all_players() -> List[Player]:
    """Every saved character, loaded fresh from disk. Used at startup to
    reconcile apartment ownership (rooms aren't persisted, so Room.owner
    has to be reconstructed from each player's saved apartment_room_vnum)
    -- not meant for hot paths, since it reads every save file."""
    ensure_dirs()
    players = []
    for filename in sorted(os.listdir(PLAYERS_DIR)):
        if filename.endswith(".json"):
            name = filename[:-len(".json")]
            player = load_player(name)
            if player:
                players.append(player)
    return players
