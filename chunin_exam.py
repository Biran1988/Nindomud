"""
Chunin Exam -- the Forest of Death scroll mechanic.

Per explicit design discussion: the simple "ask the Kage, meet a
level/mission threshold" Genin -> Chunin promotion is replaced by a
real trial, modeled on canon's Forest of Death -- a genin enters with
one of two scroll types (Heaven or Earth) and must obtain the other to
pass, either by defeating one of two dangerous "scroll guardian" mobs
deep in the forest, or by defeating ANOTHER player who's also in the
exam and taking theirs. Reaching the tower with both scrolls completes
the exam and promotes the player to Chunin on the spot.

The entry gate itself is UNCHANGED from the old Genin -> Chunin
requirement (level 15, 25 completed missions) -- this doesn't add a
new, separate gate, it changes what happens once you're qualified.
Genin are capped at 15 while awaiting promotion; older characters
who were already above that cap can still take the exam.

Other normal promotions (Special Jonin through Elite Jonin) are handled
by kage.handle_promotion_request; Village Elder is staff-appointed. Only
the Genin -> Chunin step moved out of that ladder and into this
module. See kage.py's own PROMOTION_LADDER, which no longer has a
Chunin entry, and its handle_promotion_request, which now redirects a
Genin asking about promotion to come here instead.

One shared zone (not per-village) -- canon's Chunin Exams are
explicitly an inter-village event, and a shared space is what makes
the "steal another candidate's scroll" mechanic mean anything at all
(nothing to steal if every village's genin do this in isolation).
"""

from typing import Optional

ENTRANCE_VNUM = 60000
FOREST_VNUMS = [60001, 60002, 60003]
TOWER_VNUM = 60004

HEAVEN_SCROLL = "A Heaven Scroll"
EARTH_SCROLL = "An Earth Scroll"
SCROLLS = (HEAVEN_SCROLL, EARTH_SCROLL)

HEAVEN_GUARDIAN_VNUM = 6900
EARTH_GUARDIAN_VNUM = 6901

# The exact same gate the old Genin -> Chunin ladder entry used
# (level, min_completed_missions) -- kept here as the single source of
# truth now that kage.py's own ladder no longer has a Chunin entry, so
# a future balance change only has to touch one place.
MIN_LEVEL = 15  # Genin cap: reach it before attempting the Chunin exam.
MIN_COMPLETED_MISSIONS = 25


def qualifies_for_exam(player) -> bool:
    return (
        player.village_rank == "genin"
        and player.level >= MIN_LEVEL
        and len(player.completed_missions) >= MIN_COMPLETED_MISSIONS
    )


def missing_scroll(player) -> Optional[str]:
    """Which scroll type the player still needs, or None if they
    already have both (or the given item name is neither scroll)."""
    for scroll in SCROLLS:
        if not any(item.lower() == scroll.lower() for item in player.inventory):
            return scroll
    return None


def has_both_scrolls(player) -> bool:
    return missing_scroll(player) is None


def steal_scroll_on_pvp_defeat(winner, loser) -> Optional[str]:
    """Per the PvP scroll-theft mechanic: if both players are actively
    in the exam and the loser is carrying a scroll type the winner
    doesn't have, the winner takes it. Only ever takes ONE scroll (the
    one the winner is actually missing) -- if the loser happens to be
    carrying both, the winner still only walks away with whichever one
    they needed, not a full sweep, since taking a scroll the winner
    already has would just be destroying the loser's copy for no
    reason. Returns the scroll name taken, or None if nothing changed
    hands (either player isn't in the exam, or the loser had nothing
    the winner needed)."""
    if not (winner.in_chunin_exam and loser.in_chunin_exam):
        return None
    needed = missing_scroll(winner)
    if needed is None:
        return None  # winner already has both, nothing to gain
    match = next((item for item in loser.inventory if item.lower() == needed.lower()), None)
    if match is None:
        return None
    loser.inventory.remove(match)
    winner.inventory.append(match)
    return match

# Final stage: completing the scroll trial starts a real 1v1 against a
# stronger copy with a DIFFERENT ninja class. Passing scrolls alone never
# grants Chunin rank.
def final_opponent(session):
    import combat
    p = session.player
    if not p.in_chunin_exam:
        return None
    return next((mob for mob in combat.mobs_in_room(TOWER_VNUM)
                 if getattr(mob, "chunin_exam_owner", "") == p.name
                 and mob.health > 0), None)


def begin_final_match(session):
    import combat
    import data_classes
    p = session.player
    current = final_opponent(session)
    if current:
        session.combat_target = current
        return current
    classes = [name for name in data_classes.CLASSES if name != p.primary_class]
    different_class = classes[(sum(map(ord, p.name)) + p.level) % len(classes)]
    vnum = -4_100_000 - (sum((i + 1) * ord(c) for i, c in enumerate(p.name)) % 100_000)
    level = min(250, p.level + max(5, p.level // 5))
    hp = max(125, int(p.maximum_health * 1.6))
    damage = max(5, int(p.level * 0.55 + 6))
    name = f"the {different_class} shadow of {p.name}"
    combat.register_template(vnum, name, level=level, max_health=hp,
                             min_damage=damage, max_damage=damage + max(3, p.level // 5),
                             experience_reward=0, ryo_reward=0)
    t = combat.MOB_TEMPLATES[vnum]
    t["auto_balance"] = False
    t["primary_class"] = different_class
    t["respawns"] = False
    t["act_flags"] = ["Npc", "Sentinel"]
    mob = combat.spawn_mob(vnum, TOWER_VNUM)
    mob.chunin_exam_owner = p.name
    mob.respawns = False
    mob.attacks = 2
    session.combat_target = mob
    session.send(
        f"&RThe proctor seals the exits! Your final trial begins: "
        f"{name}, a stronger version of yourself, stands before you. "
        "Defeat this opponent to become Chunin!&x"
    )
    return mob


def reset_exam(player):
    """Forfeiture/death: remove BOTH scroll types and only owned exam mob."""
    import combat
    player.in_chunin_exam = False
    player.inventory = [item for item in player.inventory
                        if not (isinstance(item, str) and
                                item.lower() in {scroll.lower() for scroll in SCROLLS})]
    for mob in list(combat.mobs_in_room(TOWER_VNUM)):
        if getattr(mob, "chunin_exam_owner", "") == player.name:
            combat.remove_mob(mob)


def finish_final_match(session, mob):
    if not session.player.in_chunin_exam or getattr(mob, "chunin_exam_owner", "") != session.player.name:
        return False
    import combat
    import data_headbands
    import kage
    import storage
    from data_villages import VILLAGES
    player = session.player
    reset_exam(player)
    combat.reset_summon_round_state(player)
    session.combat_target = None
    player.village_rank = "chunin"
    data_headbands.apply_rank_headband(player, "chunin")
    player.room_vnum = VILLAGES[player.village]["starting_room_vnum"]
    kage.announce_rank_up(player.name, "chunin")
    storage.save_player(player)
    session.send("&GYou defeat your stronger shadow in the final 1v1! The proctor names you a Chunin.&x")
    return True
