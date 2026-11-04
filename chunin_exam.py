"""
Chunin Exam -- the Forest of Death scroll mechanic.

Per explicit design discussion: the simple "ask the Kage, meet a
level/mission threshold" Genin -> Chunin promotion is replaced by a
real trial, modeled on canon's Forest of Death -- a genin enters with
one of two scroll types (Heaven or Earth, with legacy Hell accepted) and must obtain the other to
pass, either by defeating one of two dangerous "scroll guardian" mobs
deep in the forest, or by defeating ANOTHER player who's also in the
exam and taking theirs. At the central tower a protected proctor accepts both scrolls and sends
the candidate to a single-room VNUM 670 final 1v1. Victory earns Chunin rank.

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

ENTRANCE_VNUM = 45
TOWER_VNUM = 357  # Middle cell of the 25x25 Forest of Death grid.
FINAL_ARENA_VNUM = 670  # Separate, exit-less final 1v1 room.
EXAM_PROCTOR_VNUM = 6902
FOREST_VNUMS = [v for v in range(46, 670) if v != TOWER_VNUM]

HEAVEN_SCROLL = "A Heaven Scroll"
EARTH_SCROLL = "An Earth Scroll"
HELL_SCROLL = "A Hell Scroll"  # Legacy saved exam item; still accepted.
SCROLLS = (HEAVEN_SCROLL, EARTH_SCROLL)
SCROLL_ALIASES = {HEAVEN_SCROLL: (HEAVEN_SCROLL,), EARTH_SCROLL: (EARTH_SCROLL, HELL_SCROLL)}

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


def scroll_containers(player):
    """The carried inventory and every backpack's separate saved contents."""
    yield player.inventory
    for contents in getattr(player, "backpack_contents", {}).values():
        if isinstance(contents, list):
            yield contents


def _matching_scroll(container, required):
    names = {name.casefold() for name in SCROLL_ALIASES[required]}
    return next((item for item in container
                 if isinstance(item, str) and item.casefold() in names), None)


def remove_one_scroll(player, required):
    """Consume one scroll of the required type; legacy Hell counts as Earth."""
    for container in scroll_containers(player):
        item = _matching_scroll(container, required)
        if item is not None:
            container.remove(item)
            return True
    return False


def consume_both_scrolls(player):
    """Only consume when both distinct scroll classes are present."""
    if not has_both_scrolls(player):
        return False
    return all(remove_one_scroll(player, scroll) for scroll in SCROLLS)


def missing_scroll(player) -> Optional[str]:
    for required in SCROLLS:
        if not any(_matching_scroll(container, required) is not None
                   for container in scroll_containers(player)):
            return required
    return None


def has_both_scrolls(player) -> bool:
    return missing_scroll(player) is None


def steal_scroll_on_pvp_defeat(winner, loser) -> Optional[str]:
    """Steal the exact matching Heaven/Earth (or legacy Hell) item."""
    if not (winner.in_chunin_exam and loser.in_chunin_exam):
        return None
    needed = missing_scroll(winner)
    if needed is None:
        return None
    for container in scroll_containers(loser):
        item = _matching_scroll(container, needed)
        if item is not None:
            container.remove(item)
            winner.inventory.append(item)
            return item
    return None


def ensure_proctor() -> None:
    """Guarantee one protected, non-wandering exam proctor in room 357."""
    import combat
    if EXAM_PROCTOR_VNUM not in combat.MOB_TEMPLATES:
        combat.register_template(EXAM_PROCTOR_VNUM, "the Chunin Exam proctor",
                                 level=80, max_health=10000,
                                 min_damage=0, max_damage=0,
                                 experience_reward=0, ryo_reward=0)
    template = combat.MOB_TEMPLATES[EXAM_PROCTOR_VNUM]
    template["short_desc"] = "the Chunin Exam proctor"
    template["long_desc"] = "The Chunin Exam proctor waits to inspect your scrolls."
    template["description"] = (
        "The proctor guards the gate to the final trial. "
        "ASK PROCTOR EXAM or SUBMIT SCROLLS when you hold Heaven and Earth scrolls."
    )
    template["act_flags"] = ["Npc", "Sentinel", "Immortal"]
    template["enabled"] = True
    template["respawns"] = False
    template["auto_balance"] = False
    template["no_wander"] = True
    if not any(m.template_vnum == EXAM_PROCTOR_VNUM
               for m in combat.mobs_in_room(TOWER_VNUM)):
        combat.spawn_mob(EXAM_PROCTOR_VNUM, TOWER_VNUM)


def chamber_occupied(session) -> bool:
    """The one physical room hosts only one candidate's 1v1 at a time."""
    import combat
    import session as session_module
    for other in session_module.ACTIVE_SESSIONS:
        if (other is not session and other.player
                and other.player.room_vnum == FINAL_ARENA_VNUM):
            return True
    # Remove orphaned mirror NPCs left by expired sessions, never live players.
    owners = {s.player.name.casefold() for s in session_module.ACTIVE_SESSIONS
              if s.player and s.player.room_vnum == FINAL_ARENA_VNUM}
    for mob in list(combat.mobs_in_room(FINAL_ARENA_VNUM)):
        if (getattr(mob, "chunin_exam_owner", "")
                and mob.chunin_exam_owner.casefold() not in owners):
            combat.remove_mob(mob)
    return False


def start_final_trial(session) -> bool:
    """Proctor-gated passage: two scrolls -> sealed room -> mirror battle."""
    import combat
    import storage
    import world

    player = session.player
    if player.room_vnum != TOWER_VNUM:
        session.send("The final-trial proctor is at the central tower (VNUM 357).")
        return False
    if not player.in_chunin_exam or player.village_rank != "genin":
        session.send("Only Genin actively taking the Chunin Exam can enter the final trial.")
        return False
    if not any(m.template_vnum == EXAM_PROCTOR_VNUM
               for m in combat.mobs_in_room(TOWER_VNUM)):
        session.send("The proctor is not here to examine your scrolls.")
        return False
    if not has_both_scrolls(player):
        session.send(f"&YThe proctor says: Bring me both Heaven and Earth scrolls. "
                     f"You still need {missing_scroll(player)}.&x")
        return False
    if chamber_occupied(session):
        session.send("&YThe proctor says: Another candidate still occupies the final chamber. Return shortly.&x")
        return False
    if world.WORLD.get(FINAL_ARENA_VNUM) is None:
        session.send("The final chamber is unavailable. Your scrolls are safe.")
        return False
    if session.combat_target is not None or session.pvp_target is not None:
        session.send("Finish your current fight before challenging the final trial.")
        return False
    if not consume_both_scrolls(player):
        session.send("The proctor cannot verify the two scrolls.")
        return False
    player.room_vnum = FINAL_ARENA_VNUM
    player.chunin_final_ready = False
    # No helpers in an individual 1v1 arena.
    combat.dismiss_summon(player)
    session.combat_target = None
    session.pvp_target = None
    session.send("&CThe proctor accepts both scrolls and seals them away. "
                 "A transportation seal sends you to the final trial!&x")
    show_hokage_speech(session)
    storage.save_player(player)
    return True


def show_hokage_speech(session) -> None:
    """Original Heaven-and-Earth address, heard before the trial is accepted."""
    session.send(
        "&YThe Third Hokage steps into the chamber and addresses you:&x\n"
        '&W"Heaven stretches above every village, carrying the hopes of those '
        'who came before us. Earth lies beneath our feet, bearing the weight '
        'of every choice we make.\n'
        'A shinobi must understand both: dreams without action are empty, '
        'and strength without purpose has no direction.\n'
        'You brought Heaven and Earth together. Now you must face a reflection '
        'of your own strength and prove that your judgment is worthy of a Chunin."&x\n'
        '&YThe Third Hokage asks: "Are you ready for your one-on-one final trial? '
        '(yes/no)"&x'
    )


def handle_final_trial_answer(session, line: str) -> bool:
    """Keep YES/NO local to the arena; YES spawns the opponent, not combat."""
    player = getattr(session, "player", None)
    if not (player and player.in_chunin_exam and player.room_vnum == FINAL_ARENA_VNUM):
        return False
    answer = line.strip().casefold()
    if answer not in ("yes", "no", "ready"):
        return False
    if player.chunin_final_ready:
        session.send("Your shadow is already waiting. Use ATTACK SHADOW to begin, "
                     "or LEAVE CONFIRM to forfeit.")
        return True
    if answer == "no":
        session.send('&YThe Third Hokage nods. "Take the time you need. '
                     'Say YES when you are ready, or LEAVE CONFIRM to forfeit."&x')
        return True
    if answer == "ready":
        show_hokage_speech(session)
        return True
    player.chunin_final_ready = True
    if begin_final_match(session) is None:
        player.chunin_final_ready = False
        session.send("&RYour shadow could not appear. Your trial remains open; "
                     "say YES to try again.&x")
        return True
    import storage
    storage.save_player(player)
    return True


# Final stage: consenting spawns a stronger copy with a DIFFERENT ninja
# class. Combat begins only when the player chooses to attack or cast.
# Passing the scrolls alone never grants Chunin rank.
def final_opponent(session):
    import combat
    p = session.player
    if not p.in_chunin_exam:
        return None
    return next((mob for mob in combat.mobs_in_room(FINAL_ARENA_VNUM)
                 if p.room_vnum == FINAL_ARENA_VNUM
                 and getattr(mob, "chunin_exam_owner", "") == p.name
                 and mob.health > 0), None)


def begin_final_match(session):
    import combat
    import data_classes
    p = session.player
    if not p.in_chunin_exam or p.room_vnum != FINAL_ARENA_VNUM or not p.chunin_final_ready:
        return None
    current = final_opponent(session)
    if current:
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
    t["no_wander"] = True
    t["act_flags"] = ["Npc", "Sentinel"]
    mob = combat.spawn_mob(vnum, FINAL_ARENA_VNUM)
    if mob is None:
        return None
    # Preserve the challenger's likeness while remaining a tougher, different-class opponent.
    for stat in ("strength", "dexterity", "intelligence", "wisdom", "luck", "constitution"):
        setattr(mob, stat, max(10, getattr(p, stat, 10) + 5))
    mob.chakra_nature = getattr(p, "chakra_nature", None)
    mob.equipment = dict(getattr(p, "equipment", {}) or {})
    mob.chakra = mob.maximum_chakra = max(mob.maximum_chakra, getattr(p, "maximum_chakra", 0))
    mob.stamina = mob.maximum_stamina = max(mob.maximum_stamina, getattr(p, "maximum_stamina", 0))
    mob.chunin_exam_owner = p.name
    mob.respawns = False
    mob.attacks = 2
    session.send(
        f"&RThe Hokage steps back as {name}, a stronger version of yourself, "
        "materializes before you. The shadow is waiting for your first move. "
        "Use ATTACK SHADOW or target it with a jutsu to begin. "
        "Defeat this opponent to become Chunin!&x"
    )
    return mob


def reset_exam(player):
    """Forfeiture/death: remove BOTH scroll types and only owned exam mob."""
    import combat
    player.in_chunin_exam = False
    player.chunin_final_ready = False
    for container in scroll_containers(player):
        container[:] = [item for item in container
                        if not (isinstance(item, str) and
                                item.casefold() in {name.casefold() for aliases in SCROLL_ALIASES.values() for name in aliases})]
    for mob in list(combat.mobs_in_room(FINAL_ARENA_VNUM)):
        if getattr(mob, "chunin_exam_owner", "") == player.name:
            combat.remove_mob(mob)
            combat.MOB_TEMPLATES.pop(mob.template_vnum, None)


def finish_final_match(session, mob):
    if (not session.player.in_chunin_exam
            or session.player.room_vnum != FINAL_ARENA_VNUM
            or mob.room_vnum != FINAL_ARENA_VNUM
            or getattr(mob, "chunin_exam_owner", "") != session.player.name):
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
