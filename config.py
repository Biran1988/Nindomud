"""
Core configuration constants for the Naruto-Inspired ROM 2.4-style MUD.

Keeping these in one module means balance/security numbers are not
scattered through combat, chargen, or account code (Design Principle #23:
keep major systems modular and data-driven).
"""

HOST = "0.0.0.0"
PORT = 4000

# --- Accounts / security -----------------------------------------------
ADMIN_NAME = "biran"          # Reserved Implementor login (Section 33)
MUD_NAME = "NindoMUD"         # Canonical in-game display name
MIN_PASSWORD_LENGTH = 10       # Section 32
PBKDF2_ITERATIONS = 200_000
MAX_FAILED_LOGINS = 5
LOCKOUT_SECONDS = 300

# --- Character creation --------------------------------------------------
STARTING_RYO = 100             # Section 20 - granted once at creation

STARTING_HEALTH = 100
STARTING_CHAKRA = 75
STARTING_STAMINA = 100
STARTING_TRAINING_POINTS = 6  # raised from 3 (Section 132), matching the new per-level rate
STARTING_PRACTICE_POINTS = 3
MAX_ATTRIBUTE_VALUE = 75  # hard cap on any trainable attribute (str/wis/con/int/dex/luck/per/will/chakra_control)

VILLAGES = ["leaf", "stone", "water", "cloud", "sand"]
CLASSES = ["taijutsu", "ninjutsu", "genjutsu", "bukijutsu"]

STAFF_LEVELS = [
    "player",
    "helper",
    "builder",
    "area leader",
    "administrator",
    "implementor",
]

REGEN_INTERVAL_SECONDS = 40 / 3  # 75% of the old 10-second natural regen pace
IDLE_SHARINGAN_UPKEEP_INTERVAL_SECONDS = 10  # unchanged when natural regeneration slows
MISSION_COOLDOWN_SECONDS = 600  # 10 minutes -- how soon a completed mission can be repeated
APARTMENT_COST_RYO = 100_000  # one-time cost to claim an apartment; one per player
APARTMENT_EXPANSION_BASE_COST = 200_000  # 1st extra room; doubles per room already owned (200k/400k/800k/...)
APARTMENT_SELL_REFUND_PERCENT = 0.5  # 50% of whatever a room actually cost, base apartment or any expansion
PLAYER_SHOP_COST_RYO = 1_000_000  # one-time cost to claim a player shop; one per player
PLAYER_SHOP_MAX_ITEMS = 20  # max stocked items (not unique types -- see models.Player.shop_stock)
AUTOSAVE_INTERVAL_SECONDS = 120  # periodic safety-net save, on top of save-on-level-up and save-on-quit
CORPSE_DECAY_SECONDS = 300  # how long an unlooted corpse stays in the room
MOB_RESPAWN_SECONDS = 900  # 15 minutes -- how long after a mob dies before it respawns

DEFAULT_PROMPT = "&RHP:%h/%H &BCH:%c/%C &GST:%s/%S &CXP:%x/%X &YRyo:%r&x"
