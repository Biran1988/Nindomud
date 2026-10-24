"""Techniques selected from the older MUD's class roster."""

import general_skills
import time

import combat
import data_jutsu
import data_weapons
import inventory
import status_effects
import world


def dual_wield(session, words):
    player = session.player
    if not combat._can_use_jutsu(player, data_jutsu.JUTSU["dual wield"], "dual wield"):
        session.send("You have not learned Dual Wield.")
        return
    if not words:
        session.send("Usage: dual wield <weapon>. Use 'remove offhand' to stow it.")
        return
    if not player.equipment.get("wielded"):
        session.send("Wield your main weapon first.")
        return
    if player.equipment.get("tool"):
        session.send("Put away your held tool before dual wielding.")
        return
    import commands
    item = commands.find_indexed_item(" ".join(words).lower(), player.inventory)
    if item is None or commands._item_wear_loc(item) != "wielded" or not data_weapons.weapon_type_for_item(item):
        session.send("You need a carried weapon for your off hand.")
        return
    previous = player.equipment.get("offhand")
    if previous:
        ok, reason = inventory.add_item(player.inventory, previous)
        if not ok:
            session.send(inventory.full_message(reason, previous))
            return
        commands._apply_equipment_stat_bonuses(player, previous, sign=-1)
    player.inventory.remove(item)
    player.equipment["offhand"] = item
    commands._apply_equipment_stat_bonuses(player, item, sign=1)
    weapon_type = data_weapons.weapon_type_for_item(item)
    message = commands._learn_weapon_skill_if_new(player, weapon_type)
    session.send(f"You wield {item} in your off hand.")
    if message:
        session.send(message)


def chokkan(session, words):
    player = session.player
    jutsu = data_jutsu.JUTSU["chokkan"]
    if words:
        session.send("Usage: perform chokkan")
        return
    if not combat._can_use_jutsu(player, jutsu, "chokkan"):
        session.send("You have not learned Chokkan.")
        return
    import upkeep_reports
    upkeep_reports.stop_maintaining(player, "Chokkan")
    if player.chokkan_active:
        player.chokkan_active = False
        session.send("Your inner intuition fades. Chokkan is off.")
        return
    if combat._is_action_blocked(player) or session.pending_cast is not None:
        session.send("You cannot focus right now.")
        return
    if player.chakra < jutsu["chakra_cost"]:
        session.send("You need 25 Chakra to activate Chokkan.")
        return
    player.chakra -= jutsu["chakra_cost"]
    player.chokkan_active = True
    combat.grow_skill_from_usage(player, "Chokkan")
    upkeep_reports.maintain_skill(player, "Chokkan", session=session)
    session.send("You focus your inner intuition. Chokkan is on; mastered casts form signs twice as fast.")


def instant_kill(session, words, preferred_player=None):
    player = session.player
    key = "1000 years of death"
    jutsu = data_jutsu.JUTSU[key]
    if not words:
        session.send("Usage: perform 1000 years of death <target>")
        return
    if not combat._can_use_jutsu(player, jutsu, key):
        session.send("You must read the Scroll of 1000 Years of Death to learn this technique.")
        return
    if session.pending_cast is not None or combat._is_action_blocked(player) or status_effects.has_effect(player.active_status_effects, "silenced"):
        session.send("You cannot use that technique right now.")
        return
    now = time.time()
    if now < player.cooldowns.get(key, 0):
        session.send(f"1000 Years of Death is recovering ({player.cooldowns[key] - now:.1f}s).")
        return
    if player.chakra < jutsu["chakra_cost"] or player.stamina < jutsu["stamina_cost"]:
        session.send("You need 100 Chakra and 20 Stamina.")
        return

    query = " ".join(words).lower()
    mob = None if preferred_player else combat.find_mob(player.room_vnum, query)
    target_session = preferred_player
    if mob is not None:
        if mob.health <= 0:
            session.send("That target is already down.")
            return
        if any((combat.is_shopkeeper(mob), combat.is_gambler(mob), combat.is_teacher(mob), combat.is_immortal_mob(mob))):
            session.send(f"{mob.name} is protected and cannot be attacked.")
            return
    else:
        if target_session is None:
            target_session = next((s for s in session.active_sessions() if s is not session and s.player
                                   and s.player.room_vnum == player.room_vnum and query in s.player.name.lower()), None)
        if target_session is None:
            session.send("There is nobody here by that name.")
            return
        target = target_session.player
        room = world.WORLD.get(player.room_vnum)
        if room and room.safe:
            session.send("This is a PvP-safe zone.")
            return
        import hidden_mist
        if (target.health <= 0 or target.izanami_trapped or player.illusion_walk_caster is not None
                or hidden_mist.obscures(player, target)
                or general_skills.concealed_from(player, target)):
            session.send("You cannot reach that target.")
            return
        if target.kamui_intangibility_rounds_left > 0:
            session.send("Your attack passes through the intangible target.")
            return

    player.chakra -= jutsu["chakra_cost"]
    player.stamina -= jutsu["stamina_cost"]
    player.cooldowns[key] = now + jutsu["cooldown"]
    combat.grow_skill_from_usage(player, jutsu["display_name"])
    if mob:
        session.send(f"&R1000 Years of Death strikes {mob.name} down instantly!&x")
        mob.health = 0
        combat.handle_mob_defeat(session, mob)
    else:
        session.send(f"&R1000 Years of Death strikes {target.name} down instantly!&x")
        target_session.send(f"&R{player.name} uses 1000 Years of Death on you!&x")
        target.health = 0
        if combat.try_trigger_izanagi(target_session):
            return
        if combat.is_immortal_immune_to_defeat(target_session):
            combat.clamp_immortal_health(target_session)
            return
        combat.handle_pvp_defeat(session, target_session, skip_mangekyo_check=True)
