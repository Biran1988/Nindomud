"""Rank-based Academy gate for existing guard mob VNUM 24.

Existing builder-owned guards share one mob template; the same move program
therefore protects the south exit with one message regardless of whether
one or four instances stand in the room. No NPC, room or exit is fabricated.
Installed after /data world snapshots and custom mob templates are applied.
"""

GUARD_MOB_VNUM = 24
GATE_DIRECTION = "south"
REQUIRED_RANK = "genin"
GATE_MESSAGE = (
    "Academy Students cannot leave the village through the south gate. "
    "Pass your Genin Exam before heading out."
)
MARKER = "academy_south_student_rank_gate"


def install() -> dict:
    """Append one editable mob move program; preserve all saved mob fields."""
    import combat

    template = combat.MOB_TEMPLATES.get(GUARD_MOB_VNUM)
    if template is None:
        return {"mob_exists": False, "installed": False}

    programs = template.setdefault("mob_programs", [])
    # A builder may have saved a custom version of the gate already.
    # Keep their message and order rather than re-adding our default.
    for entry in programs:
        if not isinstance(entry, dict):
            continue
        if entry.get(MARKER):
            return {"mob_exists": True, "installed": False}
        if (entry.get("trigger") == "move"
                and entry.get("action") == "min_rank"):
            tokens = str(entry.get("args", "")).split()
            if len(tokens) >= 2 and tokens[0].lower() == GATE_DIRECTION and tokens[1].lower() == REQUIRED_RANK:
                return {"mob_exists": True, "installed": False}

    programs.append({
        "trigger": "move",
        "action": "min_rank",
        "args": f"{GATE_DIRECTION} {REQUIRED_RANK} {GATE_MESSAGE}",
        MARKER: True,
    })
    return {"mob_exists": True, "installed": True}
