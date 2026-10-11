"""One birth-only roll for the chakra of Indra or Ashura.

Confirmed reincarnate lines are Uchiha (Indra) and Senju/Uzumaki (Ashura).
Clan membership can change; the saved birth lineage and soul cannot.
"""

import secrets

CHANCE_DENOMINATOR = 100
LINEAGES = {"uchiha": "indra", "senju": "ashura", "uzumaki": "ashura"}
NAMES = {"indra": "Indra", "ashura": "Ashura"}
BONUS_RESOURCES = {"indra": ("chakra",), "ashura": ("health", "stamina")}
BONUS_PERCENT = 10
STARTING_ATTRIBUTE_BONUS = 5
STARTING_ATTRIBUTES = ("strength", "dexterity", "constitution", "intelligence", "wisdom",
                       "luck", "perception", "willpower", "chakra_control")


def assign_at_creation(player):
    """Mark every birth resolved; eligible births get exactly one 1/100 roll.

    Legacy Player records default to already resolved. Only the character
    factory opts a new, confirmed character into this function.
    """
    if player.reincarnation_roll_complete:
        return player.reincarnation
    player.reincarnation_roll_complete = True
    player.reincarnation_birth_clan = player.clan
    soul = LINEAGES.get(player.clan)
    if soul and secrets.randbelow(CHANCE_DENOMINATOR) == 0:
        player.reincarnation = soul
    return player.reincarnation


def display_name(player):
    return NAMES.get(player.reincarnation, "None")


def augment_resource_gain(player, resource, base_gain):
    """Add 10% to earned base resources, carrying fractions between grants.

    This runs only when creation/level-up grants new resources, never during
    load, login, stat display, training, healing, or equipment changes.
    """
    if base_gain <= 0 or resource not in BONUS_RESOURCES.get(player.reincarnation, ()):
        return base_gain
    fraction = player.reincarnation_growth_carry.get(resource, 0)
    extra, remainder = divmod(base_gain * BONUS_PERCENT + fraction, 100)
    player.reincarnation_growth_carry[resource] = remainder
    return base_gain + extra


def grant_starting_perks(player):
    import config
    if player.reincarnation_starting_perks_applied:
        return
    player.reincarnation_starting_perks_applied = True
    if player.reincarnation not in NAMES:
        return
    for attribute in STARTING_ATTRIBUTES:
        setattr(player, attribute, getattr(player, attribute) + STARTING_ATTRIBUTE_BONUS)
    for resource, base in (("health", config.STARTING_HEALTH),
                           ("chakra", config.STARTING_CHAKRA),
                           ("stamina", config.STARTING_STAMINA)):
        extra = augment_resource_gain(player, resource, base) - base
        maximum = "maximum_" + resource
        setattr(player, maximum, getattr(player, maximum) + extra)
        setattr(player, resource, getattr(player, resource) + extra)


def description(player):
    soul = player.reincarnation
    if soul not in NAMES:
        return "You are not a reincarnation of Indra or Ashura. Your creation roll is final."
    resources = "/".join(resource.title() for resource in BONUS_RESOURCES[soul])
    return (f"You are a reincarnation of {NAMES[soul]}, born to the "
            f"{player.reincarnation_birth_clan.title()} lineage. "
            f"Your lineage grants +{BONUS_PERCENT}% starting and level-up {resources}; "
            f"fractional gains carry forward. You also received +{STARTING_ATTRIBUTE_BONUS} "
            "to all nine starting attributes. This heritage is permanent.")


def command(session, args):
    if args:
        session.send("Usage: reincarnation  (your inherited soul cannot be selected or changed)")
        return
    session.send(description(session.player))
