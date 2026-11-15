"""Single, readable builder flags for ordinary NPC shop specialties.

A specialty flag implies Shopkeeper; existing saved legacy shop_type and
shopkeeper fields remain valid. Flag selection is authoritative when present.
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
# Common builder spellings all canonicalize to the documented flag.
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


def has_shop_flag(template):
    return any(flag.casefold() == "shopkeeper" or
               specialty_for_flag(flag) in SHOP_FLAGS
               for flag in template.get("act_flags", ()))


def is_shopkeeper_template(template):
    return bool(template and (template.get("shopkeeper", False) or has_shop_flag(template)))


def shop_type(template):
    if not template:
        return "general"
    for flag in template.get("act_flags", ()):
        kind = specialty_for_flag(flag)
        if kind in SHOP_FLAGS:
            return kind
    legacy = template.get("shop_type", "general")
    return legacy if legacy in SHOP_FLAGS else "general"


def set_type(template, kind):
    """One specialty per shopkeeper; preserving unrelated NPC flags."""
    if kind not in SHOP_FLAGS:
        raise ValueError("Unknown shop specialty: " + kind)
    flags = [flag for flag in template.get("act_flags", ())
             if specialty_for_flag(flag) not in SHOP_FLAGS]
    if not any(flag.casefold() == "shopkeeper" for flag in flags):
        flags.append("Shopkeeper")
    flags.append(SHOP_FLAGS[kind])
    template["act_flags"] = flags
    template["shopkeeper"] = True
    template["shop_type"] = kind
    template["shop_buys_categories"] = []


def enable_shopkeeper(template):
    flags = list(template.get("act_flags", ()))
    if "shopkeeper" not in {flag.casefold() for flag in flags}:
        flags.append("Shopkeeper")
    template["act_flags"] = flags
    template["shopkeeper"] = True


def disable_shopkeeper(template):
    template["act_flags"] = [flag for flag in template.get("act_flags", ())
                            if flag.casefold() != "shopkeeper"
                            and specialty_for_flag(flag) not in SHOP_FLAGS]
    template["shopkeeper"] = False
    template["shop_type"] = "general"


def remove_specialty(template, kind):
    template["act_flags"] = [flag for flag in template.get("act_flags", ())
                            if specialty_for_flag(flag) != kind]
    template["shop_type"] = shop_type(template) if any(
        specialty_for_flag(flag) in SHOP_FLAGS
        for flag in template.get("act_flags", ())) else "general"
    template["shop_buys_categories"] = []
