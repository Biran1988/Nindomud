"""
Customizable prompt rendering (Sections 27-31).

All built-in presets are fully colored end-to-end (every field, not just
labels) so a stock prompt never shows uncolored numbers.
"""

import leveling
from models import Player

PRESETS = {
    "default": "&RHP:%h/%H &BCH:%c/%C &GST:%s/%S &CXP:%x/%X &YRyo:%r&x",
    "basic": "&RHP:%h/%H &BCH:%c/%C &GST:%s/%S&x",
    "combat": "&RHP:%h/%H &BCH:%c/%C &GST:%s/%S &WEnemy:%e%%&x",
    "detailed": "&C[%v %k Lvl:%l]&x &RHP:%h/%H &BCH:%c/%C &GST:%s/%S &CXP:%x/%X &YRyo:%r &MMP:%m&x",
    "minimal": "&R%hH &B%cC &G%sS&x",
}

def render_prompt(player: Player, mob=None, is_staff: bool = False) -> str:
    fmt = player.prompt_string or PRESETS["default"]
    if fmt.strip().lower() == "off":
        return ""

    next_level_xp = leveling.xp_for_next_level(player.level)
    enemy_pct = ""
    enemy_name = ""
    if mob is not None and mob.max_health:
        enemy_pct = str(int(mob.health / mob.max_health * 100))
        enemy_name = mob.name

    tokens = {
        "%h": str(player.health), "%H": str(player.maximum_health),
        "%c": str(player.chakra), "%C": str(player.maximum_chakra),
        "%s": str(player.stamina), "%S": str(player.maximum_stamina),
        "%x": str(player.experience), "%X": str(next_level_xp),
        "%q": str(max(0, next_level_xp - player.experience)),
        "%r": str(player.ryo), "%m": str(player.mission_points),
        "%l": str(player.level),
        "%v": (player.village or "").capitalize(),
        "%k": (player.village_rank or "").title(),
        "%p": (player.primary_class or "").capitalize(),
        "%e": enemy_pct, "%n": enemy_name, "%t": "", "%a": "", "%d": "",
        "%E": "",
        "%V": str(player.room_vnum) if is_staff else "",
    }

    out = fmt
    # Handle the literal "%%" (percent sign) first so it isn't consumed
    # by a token substitution below.
    out = out.replace("%%", "\x00PCT\x00")
    for token, value in tokens.items():
        out = out.replace(token, value)
    out = out.replace("\x00PCT\x00", "%")
    return out
