"""Authoritative mob flags for NPC merchants; legacy saves are upgraded on load.

Builder API: ``mset <vnum> flags ShopPawnshop`` (one specialty at a time),
``mset <vnum> flags Shopkeeper`` (custom/general merchant), or
``mset <vnum> flags -Shopkeeper`` (removes the merchant role entirely).
Merchant identity and specialty come only from flags. Legacy saved fields are migration-only.
"""
SHOP_FLAGS = {
    "general": "ShopGeneral",
    "weapons": "ShopWeapons",
    "blacksmith": "ShopBlacksmith",
    "food": "ShopFood",
    "mining": "ShopMining",
    "farming": "ShopFarming",
    "lumberjack": "ShopLumberjack",
    "gemcutter": "ShopGemcutter",
    "pawnshop": "ShopPawnshop",
}
_ALIASES = {
    "weaponshop": "weapons", "armorshop": "blacksmith",
    "foodshop": "food", "miningshop": "mining",
    "farmingshop": "farming", "lumberjackshop": "lumberjack",
    "gemcuttershop": "gemcutter", "pawnshop": "pawnshop",
    "generalshop": "general", "shopkeeper": "shopkeeper",
}


def specialty_for_flag(flag):
    norm = str(flag).casefold().replace("_", "").replace("-", "")
    for kind, canonical in SHOP_FLAGS.items():
        if norm == canonical.casefold():
            return kind
    return _ALIASES.get(norm)


def canonical_flag(flag):
    kind = specialty_for_flag(flag)
    return (SHOP_FLAGS[kind] if kind in SHOP_FLAGS else
            "Shopkeeper" if kind == "shopkeeper" else None)


def explicit_specialty(template):
    """Read *only* the current flags; never a stale stored shop_type."""
    if not template:
        return None
    for flag in template.get("act_flags", ()):
        kind = specialty_for_flag(flag)
        if kind in SHOP_FLAGS:
            return kind
    return None


def has_shop_flag(template):
    return bool(template and any(
        specialty_for_flag(flag) in SHOP_FLAGS or str(flag).casefold() == "shopkeeper"
        for flag in template.get("act_flags", ())))


def is_shopkeeper_template(template):
    return has_shop_flag(template)


def specialty_from_flags(template):
    """Return the effective merchant specialty exclusively from current flags."""
    return explicit_specialty(template) or "general"


def set_type(template, kind):
    """Select one specialty and keep unrelated mob flags."""
    if kind not in SHOP_FLAGS:
        raise ValueError("Unknown shop specialty: " + kind)
    flags = [flag for flag in template.get("act_flags", ())
             if specialty_for_flag(flag) not in SHOP_FLAGS]
    if not any(str(flag).casefold() == "shopkeeper" for flag in flags):
        flags.append("Shopkeeper")
    flags.append(SHOP_FLAGS[kind])
    template["act_flags"] = flags
    template.pop("shop_type", None)
    template.pop("shopkeeper", None)
    template["shop_buys_categories"] = []


def enable_shopkeeper(template):
    flags = list(template.get("act_flags", ()))
    if not any(str(flag).casefold() == "shopkeeper" for flag in flags):
        flags.append("Shopkeeper")
    template["act_flags"] = flags
    template.pop("shop_type", None)
    template.pop("shopkeeper", None)


def disable_shopkeeper(template):
    template["act_flags"] = [flag for flag in template.get("act_flags", ())
                              if specialty_for_flag(flag) not in SHOP_FLAGS
                              and str(flag).casefold() != "shopkeeper"]
    template.pop("shop_type", None)
    template.pop("shopkeeper", None)


def remove_specialty(template, kind):
    template["act_flags"] = [flag for flag in template.get("act_flags", ())
                             if specialty_for_flag(flag) != kind]
    template.pop("shop_type", None)
    template.pop("shopkeeper", None)
    template["shop_buys_categories"] = []


def upgrade_legacy(template):
    """One-time conversion for old snapshots/templates/area packages.

    Existing merchant *flags* always win. Old boolean and text settings
    are removed to prevent later flag removal from reactivating a shop.
    This routine is called only at persistence load/import boundaries, NOT
    during live shop lookups (which would resurrect removed flags).
    """
    if not isinstance(template, dict):
        return False
    old_type = template.pop("shop_type", None)
    old_enabled = template.pop("shopkeeper", None)
    had_legacy = old_type is not None or old_enabled is not None
    if has_shop_flag(template):
        # An already flagged merchant owns its identity regardless of stale
        # legacy fields, including a stale 'pawnshop' on ShopMining.
        return had_legacy
    if old_enabled is False:
        return had_legacy
    if old_enabled is True or (old_enabled is None and old_type in SHOP_FLAGS):
        if old_type in SHOP_FLAGS and old_type != "general":
            set_type(template, old_type)
        else:
            enable_shopkeeper(template)
        return True
    return had_legacy
