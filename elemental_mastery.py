"""Innate chakra affinity and experience-based elemental mastery.

Every revealed native nature begins with full (100%) elemental affinity.
Affinity is NOT a free damage buff.  Repeated successful uses build a
separate 0-100 mastery, which gradually enhances matching elemental arts.
Never reveal an unrevealed nature in player-visible output.
"""
import random

NATURES = ("fire", "water", "wind", "earth", "lightning")
MAX_BONUS = 0.15


def known_natures(player):
    return tuple(dict.fromkeys(
        nature for nature, revealed in (
            (getattr(player, "chakra_nature", None),
             getattr(player, "chakra_nature_revealed", False)),
            (getattr(player, "chakra_nature_secondary", None),
             getattr(player, "chakra_nature_secondary_revealed", False)),
            (getattr(player, "chakra_nature_tertiary", None),
             getattr(player, "chakra_nature_tertiary_revealed", False)),
        ) if revealed and nature in NATURES
    ))


def owns_nature(player, nature):
    # Server-side permissions use ALL genuine natures even before reveal;
    # displayed/mastered progress only exposes revealed ones.
    return nature in (
        getattr(player, "chakra_nature", None),
        getattr(player, "chakra_nature_secondary", None),
        getattr(player, "chakra_nature_tertiary", None),
    ) and nature in NATURES


def current(player, nature):
    return max(0, min(100, int(getattr(player, "element_mastery", {}).get(nature, 0))))


def record_use(player, jutsu):
    """Improve the caster's actual native nature after a successful use.

    0% starts at a 25% improvement chance per successful jutsu. Growth
    progressively slows to 1% near mastery, like Sharingan progression.
    """
    nature = jutsu.get("element")
    if not nature or nature == "none" or not owns_nature(player, nature):
        return False
    progress = current(player, nature)
    if progress >= 100:
        return False
    chance = max(1, (100 - progress) // 4)
    if random.randint(1, 100) <= chance:
        player.element_mastery[nature] = progress + 1
        return True
    return False


def damage_multiplier(player, jutsu):
    """No immediate affinity bonus.  At 100% mastery, +15% technique force."""
    nature = jutsu.get("element")
    if not nature or not owns_nature(player, nature):
        return 1.0
    return 1.0 + MAX_BONUS * current(player, nature) / 100.0


def command(session, args):
    player = session.player
    revealed = known_natures(player)
    if not revealed:
        session.send("Your chakra nature is still hidden. Reveal it with Chakra Paper.")
        return
    session.send("&CElemental affinity and learned mastery:&x")
    for nature in revealed:
        pct = current(player, nature)
        session.send(f"  &W{nature.capitalize():<10}&x Affinity 100%  |  "
                     f"Mastery {pct}%  |  Effectiveness +{MAX_BONUS * pct:.2f}%")
    session.send("&DAll native elements have full affinity; actual mastery rises "
                 "only through successful use, not on revelation.&x")
