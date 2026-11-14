"""VNUM identity for individually forged gear whose visible names may repeat.

Players still carry strings and existing saves are unchanged. Newly forged gear
includes a *server-side* VNUM marker inside that saved string. Rendering hides
the marker; moves, equipping, enchantments and trade preserve it. Never use
only the display name to resolve a marked forged item.
"""
from __future__ import annotations
import re

_MARKER = re.compile(r" \[forged-vnum:(\d{1,10})\]", re.IGNORECASE)
_TRAILING_ART = re.compile(r" \[(?:element|art):[a-z_]+\]$", re.IGNORECASE)


def vnum(item: str) -> int | None:
    if not isinstance(item, str):
        return None
    matches = list(_MARKER.finditer(item))
    return int(matches[0].group(1)) if len(matches) == 1 else None


def marked(item: str) -> bool:
    return bool(isinstance(item, str) and _MARKER.search(item))


def display(item: str) -> str:
    """Strip only the internal forged identifier for all player displays."""
    return _MARKER.sub('', item) if isinstance(item, str) else item


def encode(name: str, item_vnum: int) -> str:
    if marked(name):
        raise ValueError('Item name contains reserved forged-item metadata.')
    return f'{name} [forged-vnum:{item_vnum}]'


def plain_base(item: str) -> str:
    """Original short_desc, without individual identity or ninja-art suffix."""
    return _TRAILING_ART.sub('', display(item)).casefold()


def resolve(item: str):
    """Return (vnum, prototype) for marked items, or None.

    Fail closed on invalid IDs, incorrect names, or non-forged templates.
    This prevents forged items with identical names inheriting each other's
    enchantments, provenance, stats, or durability.
    """
    import olc
    ident = vnum(item)
    if ident is None:
        return None
    proto = olc.OBJECT_TEMPLATES.get(ident)
    if (not proto or not proto.get('craft_materials')
            or proto.get('item_type') not in ('weapon', 'armor')
            or str(proto.get('short_desc', '')).casefold() != plain_base(item)):
        return None
    return ident, proto


def legacy_match(item: str):
    """Old name-only saves always resolve to the pre-duplicate original.

    A copy forged after this update carries its own VNUM. If the name is
    reused, only the original without an identifier should be consulted for
    historic name-only copies. Avoid guessing between genuinely ambiguous
    older unrelated prototypes.
    """
    import olc
    if marked(item):
        return None
    name = plain_base(item)
    matches = [(v, p) for v, p in olc.OBJECT_TEMPLATES.items()
               if str(p.get('short_desc', '')).casefold() == name]
    if not matches:
        return None
    original = [(v, p) for v, p in matches if p.get('legacy_name_owner')]
    if len(original) == 1:
        return original[0]
    if len(matches) == 1:
        return matches[0]
    # Existing unstamped duplicates are not safely attributable by name.
    return None
