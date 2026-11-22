"""Builder-only, reserved VNUM catalog for registered jutsu scrolls.

No new rooms, spawn points, shop stock, or player items are created here.
The area is builder-owned; only item prototypes are added, without overwriting
existing objects. Historical scroll VNUMs are relocated after saved templates
and spawn points are restored. Item names stay unchanged so carried copies work.
Restricted scrolls are never auto-spawned or sold, and the existing
class/bloodline/village restrictions remain authoritative when reading.
"""

from __future__ import annotations

import copy

import data_jutsu

START_VNUM = 31501
END_VNUM = 32000
CLASS_ORDER = ("general", "ninjutsu", "taijutsu", "genjutsu", "bukijutsu")
# Only a pre-existing, highly restricted scroll may be carried into the new
# catalog. It remains gated by its existing READ eligibility checks.
_EXISTING_RESTRICTED_SCROLL = "reaper death seal"
_LEGACY_SCROLLS = {
    "1000 years of death": (9810, "A Scroll of 1000 Years of Death"),
    "advanced shadow clone jutsu": (9812, "An Advanced Shadow Clone Scroll"),
    "track": (9771, "A Track Scroll"),
    "shadow shuriken technique": (9750, "A Genin Study Scroll"),
    _EXISTING_RESTRICTED_SCROLL: (9821, "A Scroll of the Reaper Death Seal"),
}
def eligible_for_catalog(key, jutsu):
    """Every registered jutsu except the explicitly unreadable beast bomb gets a VNUM.

    The beast bomb is the one explicit exception: READ always refuses it,
    because it is obtained only through tailed-beast mastery. Restricted
    bloodlines, village and class techniques remain restricted by gameplay;
    adding an item prototype neither unlocks nor auto-spawns it.
    """
    return jutsu.get("class_requirement") in CLASS_ORDER and not jutsu.get("jinchuriki_only")



# Frozen original catalog order: released scroll VNUMs are persistent IDs.
# Later new techniques are appended, never inserted into the old slots.
BASE_SCROLL_KEYS = ('1000 years of death', 'advanced shadow clone jutsu', 'advanced tracking', 'barrier', 'binding formula seal', 'black flame suppression seal', 'byakugan', 'camouflage', 'celestial byakugan', 'celestial eight trigrams judgment', 'chakra lock seal', 'chakra siphon seal', 'chakra suppression seal', 'eight trigrams mountain crusher', 'eight trigrams one hundred twenty-eight palms', 'eight trigrams palms revolving heaven', 'eight trigrams sixteen palms', 'eight trigrams sixty-four palms', 'eight trigrams thirty-two palms', 'eight trigrams three hundred sixty-one palms', 'eight trigrams twin lions crumbling attack', 'eight trigrams vacuum palm', 'eight trigrams vacuum wall palm', 'fate sight', 'flowing barrier seal', 'focused mind', 'gentle fist: chakra point strike', 'gentle fist: one blow body', 'gentle fist: tenketsu needle', 'gentle step twin lion fists', 'golden wheel reincarnation explosion', 'hand sign suppression seal', 'imbued barrier seal', 'mind suppression seal', 'multi exit barrier', 'protecting eight trigrams sixty-four palms', 'reaper death seal', 'release jutsu', 'reverse reaper seal', 'seal release', 'sealing jutsu', 'sensory detect', 'silent movement', 'silver wheel reincarnation explosion', 'summoning contract break', 'summoning contract seal', 'teleportation anchor seal', 'tenseigan chakra mode', 'timed barrier seal', 'track', 'almighty push', 'atomic dissolution', 'blast cascade', 'blast clay shot', 'blazing pulse', 'burning horizon', 'chakra ball', 'chidori', 'chishin', 'corrosive steam wave', 'deep forest bloom', 'deido bunshin', 'demonic mirroring ice crystals', 'detonation field', 'dual chidori', 'earth rasengan', 'earth wall crusher', 'fire rasengan', 'fireball jutsu', 'flash spark', 'flashfire storm', 'full body chidori', 'gale spark', 'guiding lightning', 'heat needle', 'hidden mist jutsu', 'ice prison', 'ice senbon', 'iron sand maelstrom', 'iron sand volley', 'juuha shou', 'kamui intangibility', 'kamui limb removal', 'kamui pocket dimension', 'karyuu endan', 'laser current', 'lava snare', 'lightning rasengan', 'lightning strike jutsu', 'magma torrent', 'magnetic bind', 'maximum chidori', 'mizu bunshin', 'molten pebbles', 'nanairo no rasengan', 'oodama rasengan', 'particle cage', 'particle spear', 'raikiri', 'raiton kage bunshin', 'rasengan', 'retsudotensho', 'scalding spray', 'scorching mirage', 'shadow clone jutsu', 'shadow shuriken technique', 'six paths rinnegan', 'six paths sage mode', 'six paths vital surge', 'storm dragon torrent', 'suigadan', 'suna bunshin', 'tempest lance', 'thunderhead bind', 'truth-seeking orb barrage', 'universal pull', 'ushiro shishou', 'vapor cloak burst', 'water dragon jutsu', 'water rasengan', 'water release: glue technique', 'wind blade jutsu', 'wind rasengan', 'wood binding roots', 'wood splinter barrage', 'atomic lotus strike', 'blast knuckle', 'blazing flash kick', 'choku zuki', 'cinder heel', 'daytime tiger', 'detonation rising knee', 'disintegration heel', 'dynamic entry', 'empi', 'evening elephant', 'explosive lotus barrage', 'flash ember jab', 'forest pulse palm', 'front lotus', 'frost knuckle', 'gale spark step', 'gate of death', 'gate of healing', 'gate of life', 'gate of limit', 'gate of opening', 'gate of pain', 'gate of view', 'gate of wonder', 'glacier heel', 'guiding thunder knee', 'heat mirage roundhouse', 'iron sand knuckle', 'kihon dachi', 'kumade', 'mae geri', 'magma hammer fist', 'magnetic cyclone kick', 'mirrored lotus rush', 'morning peacock', 'neko ashi dachi', 'nidan kyten geri', 'night guy', 'nova impact palm', 'oi zuki', 'particle palm', 'polar lock grip', 'pressure burst fist', 'reverse lotus', 'rootbreaker sweep', 'sanchin dachi', 'scalding palm', 'searing elbow', 'sokuto', 'solar flare fist', 'soto uke', 'storm current jab', 'stormbreaker rush', 'tamashiwara', 'tempest spiral rush', 'thornwood jab', 'thunderwind heel', 'vapor rising knee', 'volcanic axe kick', 'amaterasu', 'chisei', 'chokkan', 'demonic illusion hell viewing technique', 'devils taunt', 'distortion flame', 'greater henge', 'henge', 'illusion walk', 'insect eyes', 'izanami', 'jigaku gouka', 'jubaku satsu', 'kanashibari', 'kasumi juusha', 'kekkei no me', 'kokohi arazu', 'kokuangyou', 'kori shinchu', 'narakumi', 'nehan shouja', 'niju kokohi arazu', 'oboro bunshin', 'phantom soldiers', 'silent genjutsu', 'snakes embrace', 'soundless sound', 'suzu senbon', 'tsukuyomi', 'ultimate henge', 'counter kunai', 'demon wind shuriken', 'disenchantment', 'dual wield', 'exploding clay', 'exploding note', 'explosive tag kunai', 'fan techniques', 'flying swallow', 'multi-kunai throw', 'multi-shuriken throw', 'poison gas bomb', 'samurai sabre', 'smoke bomb', 'throw kunai', 'throw shuriken', 'toxin binding', 'trap disabling', 'weapon enchantment', 'weapon expert')

# These four follow the first released 235 and already occupy 31736-31739.
# Freeze their positions before inserting the new attack scrolls.
RELEASED_APPEND_KEYS = ("elemental shield", "fortress barrier",
                        "reinforced barrier", "sanctuary")
ATTACK_SCROLL_KEYS = ("second attack", "third attack",
                      "fourth attack", "fifth attack")

# Released 31744-31759 are immutable even when a new General jutsu is
# introduced. Future scrolls (including Kai) start at 31760.
RELEASED_ANIME_KEYS = (
    "celestial nova sphere", "dragonfire pulse", "lightning dragon cascade", "spirit cannon",
    "breathing rhythm rush", "flashstep palm", "meteor drive combo", "titanbreaker fist",
    "endless void stage", "mirrored guild hall", "phantom floor maze", "refracted memory prison",
    "comet blade finale", "ember breathing cut", "moonfang draw", "starstream sword dance",
)


# Fixed next released VNUM: 31761. Append subsequent releases after this
# instead of sorting into the already-released range.
RELEASED_NEXT_KEYS = ("kai", "trap tag placement")


def entries():
    """Keep all released IDs stable; reserve 31740-31743 for extra attacks.

    Later additions to JUTSU go AFTER these four passive scrolls rather
    than shifting an existing builder-customized object or spawn.
    """
    available = {key for key, jutsu in data_jutsu.JUTSU.items()
                 if eligible_for_catalog(key, jutsu)}
    released = [key for key in (*BASE_SCROLL_KEYS, *RELEASED_APPEND_KEYS)
                if key in available]
    if len(released) != 239:
        raise RuntimeError("Previously released Scroll Jutsu keys have changed")
    rows = [(key, data_jutsu.JUTSU[key]) for key in released]
    rows.extend((key, data_jutsu.MULTI_ATTACK_SCROLLS[key])
                for key in ATTACK_SCROLL_KEYS)
    if not set(RELEASED_ANIME_KEYS).issubset(available):
        raise RuntimeError("Previously released anime technique scrolls have changed")
    rows.extend((key, data_jutsu.JUTSU[key]) for key in RELEASED_ANIME_KEYS)
    rows.extend((key, data_jutsu.JUTSU[key]) for key in RELEASED_NEXT_KEYS)
    future = sorted(available.difference(released).difference(RELEASED_ANIME_KEYS)
                    .difference(RELEASED_NEXT_KEYS),
                    key=lambda key: (CLASS_ORDER.index(data_jutsu.JUTSU[key]["class_requirement"]),
                                     data_jutsu.JUTSU[key]["display_name"].casefold(), key))
    rows.extend((key, data_jutsu.JUTSU[key]) for key in future)
    if len(rows) > END_VNUM - START_VNUM + 1:
        raise RuntimeError("Scroll Jutsu area 31501-32000 cannot fit the current catalog")
    return tuple((START_VNUM + index, key, info)
                 for index, (key, info) in enumerate(rows))


def vnum_for(key):
    return next((vnum for vnum, name, _ in entries() if key == name), None)


def legacy_vnums():
    return {old: vnum_for(key) for key, (old, _) in _LEGACY_SCROLLS.items()}


def name_for(key):
    if key in _LEGACY_SCROLLS:
        return _LEGACY_SCROLLS[key][1]
    info = data_jutsu.MULTI_ATTACK_SCROLLS.get(key) or data_jutsu.JUTSU[key]
    return f"A Scroll of {info['display_name']}"


def _matches(proto, key):
    return (proto.get("item_type") == "scroll" and
            proto.get("scroll_jutsu") == key and
            isinstance(proto.get("short_desc"), str))


def _scroll_template(vnum, key, data):
    import olc
    obj = olc.default_object(vnum, name_for(key))
    cost = (15000 if key == "advanced shadow clone jutsu" else
            0 if key in ("1000 years of death", _EXISTING_RESTRICTED_SCROLL,
                         "shadow shuriken technique") else 500)
    description = (
        "Retired teaching scroll kept for compatibility with old builds. "
        "Second Attack is automatic at level 25; Third Attack at level 75 "
        "for EVERY class. READ is unnecessary; this item is not consumed."
        if key in ("second attack", "third attack") else
        "READ to learn a Bukijutsu-only passive numbered attack at the "
        "scroll's level requirement. Practice raises activation chance."
        if key in ("fourth attack", "fifth attack") else
        "An advanced shadow-clone technique for delegating gathering "
        "and training at a local work site. READ to learn it at level 75."
        if key == "advanced shadow clone jutsu" else
        "READ to learn Trap Tag Placement at level 25 (all classes), or "
        "at level 10 for Bukijutsu. Bukijutsu learns it automatically at level 10."
        if key == "trap tag placement" else
        "A teaching scroll inscribed with a technique. READ it to study "
        "its jutsu; existing class, bloodline, clan and element rules still apply.")
    obj.update(item_type="scroll", scroll_jutsu=key,
               level=25 if key == "trap tag placement" else int(data.get("level_requirement", 1)),
               cost=cost, description=description)
    return obj


def install(*, migrate_saved=True):
    """Merge missing prototype scrolls into the builder-owned area.

    Return summary. Existing saved non-scroll prototypes at an assigned VNUM
    are *never* replaced. Do not create rooms or add spawn points.
    """
    import olc
    import combat

    scrolls = entries()
    old_vnums = legacy_vnums()
    created, relocated, conflicts = [], [], []
    for new_vnum, key, info in scrolls:
        old_vnum = _LEGACY_SCROLLS.get(key, (None,))[0]
        old = olc.OBJECT_TEMPLATES.get(old_vnum) if old_vnum is not None else None
        existing = olc.OBJECT_TEMPLATES.get(new_vnum)
        if existing is not None and not _matches(existing, key):
            conflicts.append(new_vnum)
            continue
        # A builder's saved prototype at the old VNUM follows the technique
        # into its newly assigned VNUM. Saved new location wins if edited.
        if old and _matches(old, key):
            if existing is None or existing.get("scroll_catalog_auto"):
                obj = copy.deepcopy(old)
                obj["scroll_catalog_auto"] = False
                olc.OBJECT_TEMPLATES[new_vnum] = obj
            del olc.OBJECT_TEMPLATES[old_vnum]
            relocated.append((old_vnum, new_vnum))
        elif existing is None:
            obj = _scroll_template(new_vnum, key, info)
            obj["scroll_catalog_auto"] = True
            olc.OBJECT_TEMPLATES[new_vnum] = obj
            created.append(new_vnum)

    # Update NPC stocks that point to the retired VNUMs, preserving order and
    # any other builder-selected goods. No new item is offered automatically.
    usable_remaps = {old: new for old, new in old_vnums.items()
                     if old not in olc.OBJECT_TEMPLATES
                     and _matches(olc.OBJECT_TEMPLATES.get(new, {}),
                                  next(k for k, (n, _) in _LEGACY_SCROLLS.items() if n == old))}
    for mob in combat.MOB_TEMPLATES.values():
        if "shop_items" in mob:
            mob["shop_items"] = [usable_remaps.get(vnum, vnum)
                                 for vnum in mob["shop_items"]]

    # Move saved spawn-point references; otherwise a restarted server would
    # still point at the old VNUM even though this release stops creating it.
    if migrate_saved and usable_remaps:
        import storage
        state = storage.load_spawn_points()
        points = state.get("points", {})
        changed = False
        for key, point in list(points.items()):
            if point.get("kind") != "item" or point.get("vnum") not in usable_remaps:
                continue
            new = usable_remaps[point["vnum"]]
            renamed = f"item:{new}:{point['room_vnum']}"
            if renamed not in points:
                updated = dict(point)
                updated["vnum"] = new
                points[renamed] = updated
            del points[key]
            changed = True
        if changed:
            storage.save_spawn_points(state)
        # Remove outdated spawn prototype snapshots and migrate metadata.
        saved = storage.load_custom_templates()
        templates = saved.get("items", {})
        touched = False
        for old, new in usable_remaps.items():
            source = templates.get(str(old))
            if source and _matches(source, next(k for k, (n, _) in _LEGACY_SCROLLS.items() if n == old)):
                templates.setdefault(str(new), copy.deepcopy(olc.OBJECT_TEMPLATES[new]))
                del templates[str(old)]
                touched = True
        if touched:
            storage.save_custom_templates(saved)

        # Retire the historical IDs from the persisted world snapshot too.
        # Patch only the affected item prototypes and shop stock references;
        # leave the builder's 31501-32000 area, rooms and other /data alone.
        world_state = storage.load_world_state()
        if world_state and relocated:
            snapshot_items = world_state.setdefault("items", {})
            snapshot_changed = False
            for old, new in relocated:
                if str(old) in snapshot_items:
                    snapshot_items.pop(str(old))
                    snapshot_changed = True
                if new in olc.OBJECT_TEMPLATES and str(new) not in snapshot_items:
                    snapshot_items[str(new)] = copy.deepcopy(olc.OBJECT_TEMPLATES[new])
                    snapshot_changed = True
            for saved_mob in world_state.get("mobs", {}).values():
                old_stock = saved_mob.get("shop_items")
                if old_stock:
                    new_stock = [usable_remaps.get(vnum, vnum) for vnum in old_stock]
                    if new_stock != old_stock:
                        saved_mob["shop_items"] = new_stock
                        snapshot_changed = True
            if snapshot_changed:
                storage.save_world_state(world_state)

    if migrate_saved and (created or relocated):
        import world_autosave
        world_autosave.mark_dirty()
    if conflicts:
        print("[Scroll Jutsu] Preserved existing builder objects at occupied VNUMs: "
              + ", ".join(map(str, conflicts)))
    return {"created": len(created), "moved": tuple(relocated),
            "conflicts": tuple(conflicts), "total": len(scrolls)}
