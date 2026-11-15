"""Per-item job tool durability stored in the item's own inventory name.

Inventory and equipment store plain strings, so a worn tool carries its
remaining uses as a suffix. This travels with the item through saving,
dropping, backpacks, and direct player trades without tracking positions
in an inventory that can be reordered or stacked.
"""

import re


DEFAULT_USES = 250
_USES_SUFFIX = re.compile(r" \[(\d+)/(\d+) uses\]$", re.IGNORECASE)
_DIAMOND_SUFFIX = re.compile(r" \[diamond\]$", re.IGNORECASE)


def base_name(item_name: str) -> str:
    """Strip only this module's trailing durability annotation."""
    return _DIAMOND_SUFFIX.sub("", _USES_SUFFIX.sub("", item_name))


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
    import item_balance
    total = item_balance.effective_uses(proto) if proto else DEFAULT_USES
    total = max(1, total)
    return total, total


def has_diamond(item_name: str) -> bool:
    """True only for this individually diamond-inlaid tool."""
    return bool(_DIAMOND_SUFFIX.search(_USES_SUFFIX.sub("", item_name)))


def with_diamond(item_name: str) -> str | None:
    """Double actual remaining and maximum uses once, with a saved marker."""
    if has_diamond(item_name):
        return None
    remaining, total = uses_left(item_name)
    if remaining <= 0:
        return None
    return f"{base_name(item_name)} [diamond] [{remaining * 2}/{total * 2} uses]"


def display_name(item_name: str) -> str:
    """Only display the genuine name; tool uses appear under EXAMINE."""
    return base_name(item_name)


def spend_use(item_name: str) -> str | None:
    """Consume one attempt; return updated item name, or None on break."""
    remaining, total = uses_left(item_name)
    if remaining <= 1:
        return None
    marker = " [diamond]" if has_diamond(item_name) else ""
    return f"{base_name(item_name)}{marker} [{remaining - 1}/{total} uses]"
