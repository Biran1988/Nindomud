"""Persistent anti-alt provenance checks for uniquely forged equipment.

Store provenance on the server-side item prototype, never in the visible item
name, EXAMINE, shops or chat. IP is the canonical, trusted TCP peer reported
by the server. Only the original character is exempt from its own IP stamp.
Other characters connecting from that same IP may not receive the item.
"""
from __future__ import annotations

import ipaddress

DENIED = "That crafted item cannot be transferred to this character."


def canonical_ip(raw) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = ipaddress.ip_address(raw.strip().split("%", 1)[0])
    except ValueError:
        return None
    if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped:
        parsed = parsed.ipv4_mapped
    return str(parsed)


def stamp(proto: dict, session) -> None:
    """Bind verified creator identity once, without adding name metadata.

    Live server connections always supply connection_ip. Tooling/test
    sessions without a network peer retain the creator name but are marked
    unverified; they cannot provide a genuine IP assertion.
    """
    if proto.get("crafted_by_character"):
        return
    proto["crafted_by_character"] = session.player.name
    proto["crafted_by_ip"] = canonical_ip(getattr(session, "connection_ip", None)) or ""


def verified_ip(recipient, *, session=None) -> str | None:
    if session is not None:
        # Do not fall back to a stale saved address for a live connection.
        return canonical_ip(getattr(session, "connection_ip", None))
    return canonical_ip(getattr(recipient, "last_connection_ip", None))


def stamped_prototype(item_name: str):
    """Resolve exact unique item identity; unknown/duplicate is not trusted."""
    import olc
    import ninja_arts
    name = ninja_arts.base_item(item_name)
    matches = [p for p in olc.OBJECT_TEMPLATES.values()
               if (p.get("short_desc", "").casefold() == name.casefold()
                   or name.casefold() in {
                       str(previous).casefold()
                       for previous in p.get("previous_short_descs", [])
                   })]
    return matches[0] if len(matches) == 1 else None


def denied(item_name: str, recipient, *, session=None) -> bool:
    """Fail closed for stamped items whose recipient address is unknown."""
    proto = stamped_prototype(item_name)
    if not proto:
        return False
    maker_ip = canonical_ip(proto.get("crafted_by_ip"))
    maker_name = str(proto.get("crafted_by_character", "")).casefold()
    if not maker_name or not maker_ip:
        return False  # Legacy or network-unverified crafting cannot be compared.
    if getattr(recipient, "name", "").casefold() == maker_name:
        return False
    current_ip = verified_ip(recipient, session=session)
    return current_ip is None or current_ip == maker_ip


def message(item_name: str, recipient, *, session=None) -> str | None:
    return DENIED if denied(item_name, recipient, session=session) else None
