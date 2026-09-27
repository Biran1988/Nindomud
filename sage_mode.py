"""Elder-taught Sage Mode for each summoning family.

Ninken, slug, and monkey Sage Modes are game extensions of the summon
contracts; the slow nature-energy training follows the toad/snake theme.
"""
import random
import time

import data_summons
import combat
MIN_LEVEL = 80
TRAIN_INTERVAL = 60 * 60
TRAIN_SUCCESS_PERCENT = 5
MASTERY_REQUIRED = 100
IDLE_CHAKRA_UPKEEP = 12  # every 10 seconds while online and out of combat
COMBAT_CHAKRA_UPKEEP = 16  # each combat round
COMBAT_STAMINA_UPKEEP = 8
SUMMON_COST = 40


def active_contract(player):
    contract = player.sage_active_contract
    if (contract in data_summons.CONTRACTS
            and contract in player.signed_summoning_contracts
            and player.sage_mastery.get(contract, 0) >= MASTERY_REQUIRED):
        return contract
    return ""


def outgoing(player, damage, jutsu=False, weapon=False):
    contract = active_contract(player)
    if not contract:
        return damage
    bonus = 20 + (10 if contract == "snake" and jutsu else 0) + (10 if contract == "monkey" and weapon else 0)
    return max(1, damage * (100 + bonus) // 100)


def accuracy(player):
    contract = active_contract(player)
    return 10 + (5 if contract == "toad" else 0) if contract else 0


def dodge(player):
    return 10 if active_contract(player) == "ninken" else 0


def incoming(player, damage):
    return max(0, damage * 90 // 100) if active_contract(player) else damage


def combat_pulse(session):
    player = session.player
    contract = active_contract(player)
    if not contract:
        if player.sage_active_contract:
            player.sage_active_contract = ""
            session.send("Your Sage Mode ends because its contract or mastery is no longer valid.")
        return
    if player.chakra < COMBAT_CHAKRA_UPKEEP or player.stamina < COMBAT_STAMINA_UPKEEP:
        player.sage_active_contract = ""
        session.send("Your chakra and stamina give out -- your Sage Mode fades.")
        return
    player.chakra -= COMBAT_CHAKRA_UPKEEP
    player.stamina -= COMBAT_STAMINA_UPKEEP
    session.send(f"Your Sage Mode uses {COMBAT_CHAKRA_UPKEEP} chakra and {COMBAT_STAMINA_UPKEEP} stamina to remain active.")
    if contract == "slug" and player.health > 0:
        amount = min(player.maximum_health - player.health, max(1, player.maximum_health // 20))
        if amount > 0:
            player.health += amount
            session.send(f"Slug Sage Mode restores {amount} health.")


def idle_upkeep(session):
    """Called on the same 10-second, out-of-combat timer as Sharingan."""
    player = session.player
    if not player.sage_active_contract:
        return
    if not active_contract(player) or player.chakra < IDLE_CHAKRA_UPKEEP:
        player.sage_active_contract = ""
        session.send("Your chakra gives out -- your Sage Mode fades.")
        return
    player.chakra -= IDLE_CHAKRA_UPKEEP
    session.send(f"Your Sage Mode uses {IDLE_CHAKRA_UPKEEP} chakra to remain active.")


def elder_families(player):
    """Only living, builder-configured elders in the current room count."""
    families = set()
    for mob in combat.mobs_in_room(player.room_vnum):
        template = combat.MOB_TEMPLATES.get(mob.template_vnum, {})
        family = template.get("summon_family", "")
        if mob.health > 0 and "SummonElder" in template.get("act_flags", []) and family in data_summons.CONTRACTS:
            families.add(family)
    return families


def command(session, args):
    player = session.player
    if args and args[0].lower() == "status":
        lines = ["Sage Mode training (each family is mastered separately):"]
        for key, info in data_summons.CONTRACTS.items():
            pct = max(0, min(100, player.sage_mastery.get(key, 0)))
            lines.append(f"  {info['display_name']}: {pct}% -- {info['hideout_name']}")
        lines.append(f"Active: {active_contract(player) or 'none'}")
        lines.append("Use sage train at an elder; sage [on <family>] toggles your mastered mode.")
        session.send("\n".join(lines))
        return
    action = args[0].lower() if args else "toggle"
    if action == "off" or (action == "toggle" and active_contract(player)):
        if not active_contract(player):
            session.send("You are not in Sage Mode.")
            return
        player.sage_active_contract = ""
        session.send("You release your Sage Mode.")
        return
    if action not in ("train", "on", "activate", "toggle") and action not in data_summons.CONTRACTS:
        session.send("Usage: sage [on <family>|off|status] | sage train [family]")
        return
    if action == "train" and (session.combat_target or session.pvp_target):
        session.send("You must finish fighting first.")
        return
    if action == "train":
        families = elder_families(player)
        contract = args[1].lower() if len(args) > 1 else (next(iter(families)) if len(families) == 1 else None)
        if contract not in families and families:
            session.send("Choose an elder here: sage train <" + "|".join(sorted(families)) + ">")
            return
        if contract is None:
            session.send("Only a summon elder at their hideout can teach Sage Mode.")
            return
    else:
        if action in ("on", "activate"):
            contract = args[1].lower() if len(args) > 1 else player.sage_preferred_contract
        else:
            contract = player.sage_preferred_contract if action == "toggle" else action
        if not contract:
            mastered = [key for key in data_summons.CONTRACTS if key in player.signed_summoning_contracts
                        and player.sage_mastery.get(key, 0) >= MASTERY_REQUIRED]
            contract = mastered[0] if len(mastered) == 1 else ""
        if contract not in data_summons.CONTRACTS:
            session.send("Choose a mastered family: sage on <toad|snake|slug|ninken|monkey>.")
            return
    if contract not in player.signed_summoning_contracts:
        session.send("You must sign this family's summoning contract first.")
        return
    if action == "train":
        if player.level < MIN_LEVEL:
            session.send(f"The elder will only teach a level {MIN_LEVEL} shinobi.")
            return
        pct = max(0, min(100, player.sage_mastery.get(contract, 0)))
        if pct >= MASTERY_REQUIRED:
            session.send("You have already mastered this family's Sage Mode.")
            return
        now = time.time()
        ready = player.sage_training_ready_at.get(contract, 0)
        if now < ready:
            session.send(f"The elder asks you to meditate longer. Try again in {int((ready - now + 3599) // 3600)} hours.")
            return
        player.sage_training_ready_at[contract] = now + TRAIN_INTERVAL
        if random.randint(1, 100) <= TRAIN_SUCCESS_PERCENT:
            player.sage_mastery[contract] = pct + 1
            session.send(f"The {contract} elder guides you through stillness and natural energy. {contract.title()} Sage mastery: {pct + 1}%." +
                         (" You can now activate this Sage Mode!" if pct + 1 == 100 else ""))
        else:
            session.send(f"The {contract} elder steadies your unstable natural energy. You learn from the attempt, but mastery remains {pct}%.")
        return
    if player.sage_mastery.get(contract, 0) < MASTERY_REQUIRED:
        session.send(f"You must reach 100% mastery with the {contract} elder first.")
        return
    if active_contract(player):
        session.send("You are already in Sage Mode. Use 'sage off' before choosing another family.")
        return
    required_chakra = COMBAT_CHAKRA_UPKEEP if session.combat_target or session.pvp_target else IDLE_CHAKRA_UPKEEP
    if player.chakra < required_chakra or player.stamina < COMBAT_STAMINA_UPKEEP:
        session.send("You need chakra and stamina to sustain Sage Mode.")
        return
    player.sage_active_contract = contract
    player.sage_preferred_contract = contract
    session.send(f"You gather natural energy and enter {contract.title()} Sage Mode. Use 'sage off' to release it.")


def summon_command(session, args):
    player = session.player
    if args and args[0].lower() == "dismiss":
        if session.combat_target or session.pvp_target:
            session.send("You cannot dismiss a summon while fighting.")
            return
        if combat.dismiss_summon(player):
            session.send("You dismiss your summon.")
        else:
            session.send("You have no summon to dismiss.")
        return
    if args and args[0].lower() == "sign":
        sign_command(session, args[1:])
        return
    if not args or args[0].lower() not in data_summons.CONTRACTS:
        session.send("Usage: summon <toad|snake|slug|ninken|monkey> | summon sign [family] | summon dismiss")
        return
    contract = args[0].lower()
    if contract not in player.signed_summoning_contracts:
        session.send("You have not signed that summoning contract.")
        return
    if session.combat_target or session.pvp_target:
        session.send("You cannot change summons while fighting.")
        return
    tier = data_summons.best_available_tier(contract, player.level)
    if tier is None or player.chakra < SUMMON_COST:
        session.send(f"You need level 20 and {SUMMON_COST} chakra to summon this family.")
        return
    player.chakra -= SUMMON_COST
    combat.dismiss_summon(player)
    summon = combat.spawn_summon(player, tier)
    session.send(f"You summon {summon.name} to fight beside you.")


def sign_command(session, args=None):
    player = session.player
    if session.combat_target or session.pvp_target:
        session.send("You must finish fighting first.")
        return
    families = elder_families(player)
    contract = args[0].lower() if args else (next(iter(families)) if len(families) == 1 else None)
    if contract not in families and families:
        session.send("Choose an elder here: summon sign <" + "|".join(sorted(families)) + ">")
        return
    if contract is None:
        session.send("Find the summon family's hidden sanctuary to sign its contract.")
    elif player.level < data_summons.CONTRACTS[contract]["unlock_level"]:
        session.send("You must reach level 20 to sign a summoning contract.")
    elif contract in player.signed_summoning_contracts:
        session.send("You have already signed this contract.")
    else:
        player.signed_summoning_contracts.append(contract)
        session.send(f"You sign the {contract.title()} summoning contract before its elder. Use 'summon {contract}' to call a partner.")
