"""Per-item job tool durability stored in the item's own inventory name.

Inventory and equipment store plain strings, so a worn tool carries its
remaining uses as a suffix. This travels with the item through saving,
dropping, backpacks, and direct player trades without tracking positions
in an inventory that can be reordered or stacked.
"""

import re


DEFAULT_USES = 250
_USES_SUFFIX = re.compile(r" \[(\d+)/(\d+) uses\]$", re.IGNORECASE)


def base_name(item_name: str) -> str:
    """Strip only this module's trailing durability annotation."""
    return _USES_SUFFIX.sub("", item_name)


def uses_left(item_name: str) -> tuple:
    """Return (remaining, total) for one tool, including pristine tools."""
    match = _USES_SUFFIX.search(item_name)
    if match:
        remaining, total = int(match.group(1)), int(match.group(2))
        return max(0, min(remaining, total)), max(1, total)

    import olc
    base = base_name(item_name).lower()
    proto = next((p for p in olc.OBJECT_TEMPLATES.values()
                  if p.get("short_desc", "").lower() == base), None)
    if proto is None:
        proto = next((p for p in olc.OBJECT_TEMPLATES.values()
                      if p.get("item_type") == "tool" and p.get("short_desc", "").lower() in base), None)
    total = proto.get("max_uses", DEFAULT_USES) if proto else DEFAULT_USES
    total = max(1, total)
    return total, total


def display_name(item_name: str) -> str:
    """Show remaining uses even on a tool that has never been used."""
    import olc
    base = base_name(item_name).lower()
    if not any(p.get("item_type") == "tool" and p.get("short_desc", "").lower() in base
               for p in olc.OBJECT_TEMPLATES.values()):
        return item_name
    remaining, total = uses_left(item_name)
    return f"{base_name(item_name)} [{remaining}/{total} uses]"


def spend_use(item_name: str) -> str | None:
    """Consume one attempt; return updated item name, or None on break."""
    remaining, total = uses_left(item_name)
    if remaining <= 1:
        return None
    return f"{base_name(item_name)} [{remaining - 1}/{total} uses]"
