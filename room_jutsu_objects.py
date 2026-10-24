"""Visible, untakeable room objects derived from live lingering jutsu.

No inventory entries or separate timers: ending, extinguishing or expiring
the underlying effect immediately removes its object from every room view.
"""
from dataclasses import dataclass
import time


@dataclass(frozen=True)
class JutsuObject:
    name: str
    keywords: str
    room_line: str
    description: str


def active_objects(room):
    if room is None:
        return []
    now = time.time()
    objects = []
    import hidden_mist
    if hidden_mist.room_active(room):
        objects.append(JutsuObject(
            "&CA Shroud of Hidden Mist&x", "mist shroud hidden mist jutsu fog",
            "&CA dense hidden mist swirls here, veiling the room in pale chakra.&x",
            "Thick, chakra-laden mist curls around everything in sight. Shapes "
            "vanish into its depths, concealing the ninja who formed it."))
    if (room.amaterasu_fire_caster and room.amaterasu_fire_expires_at > now):
        objects.append(JutsuObject(
            "&[141]The Black Flames of Amaterasu&x", "black flames amaterasu fire inferno",
            "&[141]The black flames of Amaterasu writhe here, edged in crimson.&x",
            "Unnatural black fire clings to the surroundings, its crimson edges "
            "flickering without mercy. The room itself is ablaze; "
            "these flames remain until they fade or their caster extinguishes them."))
    if (room.kekkei_no_me_caster and room.kekkei_no_me_expires_at > now):
        element = room.kekkei_no_me_element or "raw"
        color = {"fire": "&[208]", "water": "&[39]", "wind": "&[159]",
                 "earth": "&[178]", "lightning": "&[226]"}.get(element, "&M")
        objects.append(JutsuObject(
            f"{color}Kekkei no Me's {element.title()} Chakra Domain&x",
            f"kekkei no me barrier eye {element} chakra domain field",
            f"{color}A shimmering {element} chakra domain saturates the room.&x",
            f"Kekkei no Me has flooded this place with {element} chakra. "
            "Its oppressive pressure drains intruders while empowering its caster."))
    if room.temp_description_text and room.temp_description_until > now:
        objects.append(JutsuObject(
            "&[180]Lingering Jutsu Aftermath&x",
            "lingering elemental jutsu chakra clash aftermath " + room.temp_description_text.lower(),
            f"&[180]{room.temp_description_text}&x",
            room.temp_description_text))
    return objects


def find(room, query):
    """Match natural object keywords, including 'black flames' and 'mist'."""
    words = [word for word in query.lower().replace("'s", "").split()
             if word not in {"a", "an", "the", "of"}]
    if not words:
        return None
    return next((obj for obj in active_objects(room)
                 if all(word in obj.keywords.split() for word in words)), None)
