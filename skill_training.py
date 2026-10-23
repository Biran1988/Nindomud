"""Permanent teacher-practice introductions for ordinary learned skills."""
import data_jutsu
import data_passives


def exempt_by_design(skill_name: str) -> bool:
    if data_passives.is_passive(skill_name):
        return True
    return any(
        jutsu["display_name"].lower() == skill_name.lower()
        and (jutsu.get("scroll_only") or jutsu.get("kkg_gate")
             or jutsu.get("jutsu_type") in (
                 "combat_passive", "counter", "silent_genjutsu_passive"))
        for jutsu in data_jutsu.JUTSU.values()
    )


def mark_practiced(player, skill_name: str) -> None:
    """Remember one successful paid teacher session, even after mastery loss."""
    names = getattr(player, "practiced_skills", None)
    if names is not None and skill_name not in names:
        names.append(skill_name)


def grant_without_practice(player, skill_name: str) -> None:
    """Remember skills awarded by scroll or other explicit rewards."""
    names = getattr(player, "practice_exempt_skills", None)
    if names is not None and skill_name not in names:
        names.append(skill_name)


def needs_first_practice(player, skill_name: str) -> bool:
    if not getattr(player, "practice_gate_enabled", False):
        return False
    # Staff mastery is an authenticated session privilege, not a permanent
    # teacher lesson or a bypass inferred from proficiency/player save fields.
    # Keep it here so general utilities and direct commands share the exemption.
    from session import ACTIVE_SESSIONS
    if any(getattr(s, "player", None) is player
           and getattr(getattr(s, "account", None), "staff_level", "player") != "player"
           for s in ACTIVE_SESSIONS):
        return False
    if skill_name not in getattr(player, "learned_skills", ()):
        return False
    if exempt_by_design(skill_name) or skill_name in getattr(player, "practice_exempt_skills", ()):
        return False
    return skill_name not in getattr(player, "practiced_skills", ())
