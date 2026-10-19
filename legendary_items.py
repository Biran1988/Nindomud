"""
Legendary items sold by every village's Kage (Section 76) -- per
direct request ("Make the Kage sell legendary iconic items from
Naruto that cost large amounts of mission points but give special
perks and very good stat boosts...start with only armor like Naruto
jacket gaaras gourd color them flamboyance but appropriate to the
item").

Confirmed design, via direct follow-up: "special perks" means flat
stat bonuses (hitroll/damroll/AC/max HP-chakra-stamina/attributes),
much larger than ordinary crafted gear -- the existing item stat-bonus
mechanism (oset statbonus, see olc.STAT_BONUS_KEYS), not a new kind of
mechanic. Purchasable by ANY player with enough mission points, not
Kage-gated -- matching the existing village_perks.py buff-purchase
pattern (see commands.cmd_buy's own _own_kage_chamber branch), which
the user separately confirmed is deliberately open to everyone, not
restricted to the Kage.

Per a direct follow-up request ("Add a total of 10 items and it's ok
to reference character names in items like kakashi mask"), expanded
from the original 2 items to 10, and explicitly permitted to name
items directly after characters from here on (Kakashi's Mask,
Itachi's Ring, and so on) -- a deliberate change from the first 2
items, which stayed inspired-by-only (matching this project's own
prior convention that canon character NAMES are blocked at character
creation) before this follow-up explicitly lifted that restriction
for item naming specifically. "Color them flamboyant but appropriate
to the item" is achieved through each item's own descriptive language
and stat theme rather than raw color codes embedded in the name --
every item here is set to rarity "legendary" (see data_rarity.py),
which already wraps the whole name in a vivid orange/gold color and a
two-tone bracketed tag automatically, everywhere the name is shown;
embedding additional color codes directly into short_desc would
conflict with that existing wrapping, since short_desc is also used
verbatim in room/inventory listings that don't go through the
rarity-colored path.

Registered into olc.OBJECT_TEMPLATES once at server start (content.py),
same as every other piece of shipped item content -- there's no
separate persistence layer for these, they're just prototypes like any
other 'oset create' item, purchasable via a new branch in cmd_buy
alongside the existing village-perk purchase flow.

Fully rebuilt to a specific 20-item roster per a direct follow-up
request naming an exact character-to-item pairing for each of 20
named characters -- confirmed to REPLACE any item that conflicted
with an earlier version of this roster (e.g. Tsunade's item became a
necklace, not gloves; Jiraiya's became a forehead protector, not the
toad scroll from an even earlier follow-up) rather than keep both.
Three brand-new wear slots (neck/piercing/back) were added to
olc.WEAR_LOCATIONS/ARMOR_WEAR_LOCATIONS specifically to support this
list -- Tsunade's necklace needed a neck slot that didn't exist
anywhere in the game before this, and a follow-up confirmed spreading
Gaara's gourd to a new back slot and Pain's piercings to their own
dedicated slot rather than letting an otherwise very head-slot-heavy
roster (masks, glasses, bandages, and so on) crowd that one slot even
further. Every other part of the equipment system (wear/wield,
'equipment' display, wear_loc validation) already worked generically
off these two sets with no hardcoded slot list anywhere, confirmed
directly before trusting that adding to them was the complete fix
needed.
"""

# Vnum range 9751-9770 reserved for legendary Kage-sold items --
# sits right next to the existing Genin Study Scroll (9750), in the
# same "real shipped item content" neighborhood, rather than a
# scratch-test range. Verified clean both by grepping every literal
# create-call vnum across the whole codebase AND by checking the
# real, live registered state after content.populate(), not by
# source-text grep alone.
#
# Full 20-item roster rebuilt per a direct, explicit list -- one
# specific item per named character. Where a character/item pairing
# from an earlier version of this roster survived unchanged (Naruto,
# Kakashi's mask, Kakashi's blade), its original vnum was kept;
# everything else was reassigned cleanly across this rebuild rather
# than left with gaps or an inconsistent mix of old and new numbering.
LEGENDARY_ITEMS = {
    "naruto's jacket": {
        "vnum": 9751,
        "short_desc": "Naruto's Orange Jacket",
        "long_desc": "A brilliant orange-and-blue battle jacket lies here, its spiral emblem catching the light.",
        "description": (
            "A blazing orange jacket with deep blue trim and a swirling crest stitched "
            "over the heart -- worn by a legendary knucklehead ninja who never gave up, "
            "no matter the odds. Wearing it seems to steady the nerves and stiffen the "
            "resolve of anyone who puts it on."
        ),
        "item_type": "armor",
        "wear_loc": "body",
        "cost_mission_points": 500,
        "stat_bonuses": {
            "max_health": 150,
            "max_chakra": 100,
            "constitution": 5,
            "armor_class": -10,
        },
    },
    "sasuke's uchiha shirt": {
        "vnum": 9752,
        "short_desc": "Sasuke's Uchiha Clan Shirt",
        "long_desc": "A dark blue shirt lies here, the Uchiha clan crest stitched sharply on its back.",
        "description": (
            "A dark, high-collared shirt bearing the Uchiha clan's fan-shaped crest -- "
            "worn by an avenger whose talent was matched only by the weight of what he "
            "carried. Wearing it sharpens the edges of every strike, as though something "
            "in the fabric itself refuses to hold back."
        ),
        "item_type": "armor",
        "wear_loc": "body",
        "cost_mission_points": 500,
        "stat_bonuses": {
            "hitroll": 6,
            "damroll": 6,
            "dexterity": 4,
        },
    },
    "kakashi's mask": {
        "vnum": 9753,
        "short_desc": "Kakashi's Face Mask",
        "long_desc": "A worn ninja mask lies here, its lower half designed to hide everything but a single sharp eye.",
        "description": (
            "A simple cloth mask that covers the lower half of the face, leaving only the "
            "eyes exposed -- worn for years by a famous Copy Ninja who kept far more "
            "hidden than his face. There's something quietly unnerving about how easily it "
            "reads an opponent's next move before they've even committed to it."
        ),
        "item_type": "armor",
        "wear_loc": "head",
        "cost_mission_points": 500,
        "stat_bonuses": {
            "hitroll": 6,
            "intelligence": 5,
            "wisdom": 3,
        },
    },
    "gaara's sand gourd": {
        "vnum": 9754,
        "short_desc": "Gaara's Sand Gourd",
        "long_desc": "A massive gourd rests here, sand hissing faintly within as though it were alive.",
        "description": (
            "An enormous gourd, sealed shut and strapped for the back, filled with sand "
            "that shifts and whispers even when perfectly still. Carried by a solitary "
            "jinchuriki who let almost nothing -- and almost no one -- close enough to "
            "matter. Its weight is nothing to a strong enough back, and its presence "
            "alone seems to unsettle anyone foolish enough to get close."
        ),
        "item_type": "armor",
        "wear_loc": "back",
        "cost_mission_points": 500,
        "stat_bonuses": {
            "max_health": 100,
            "armor_class": -20,
            "damroll": 8,
            "dexterity": 3,
        },
    },
    "kankuro's face paint": {
        "vnum": 9755,
        "short_desc": "Kankuro's Face Paint",
        "long_desc": "A small container of dark purple face paint sits here, its hood folded neatly beside it.",
        "description": (
            "Dark purple face paint paired with a heavy hood, worn by a puppeteer who "
            "preferred watching from a careful distance over getting his own hands dirty. "
            "Wearing it sharpens the eye for weakness and leaves opponents second-guessing "
            "exactly where the real threat is coming from."
        ),
        "item_type": "armor",
        "wear_loc": "head",
        "cost_mission_points": 500,
        "stat_bonuses": {
            "intelligence": 6,
            "luck": 5,
            "armor_class": -8,
        },
    },
    "jiraiya's forehead protector": {
        "vnum": 9756,
        "short_desc": "Jiraiya's Oil Forehead Protector",
        "long_desc": "A weathered forehead protector lies here, faintly stained with something that smells like hair oil.",
        "description": (
            "A well-worn forehead protector, faintly stained from years of careless "
            "handling -- worn by one of the most powerful and shamelessly eccentric "
            "shinobi ever to earn the title of Sannin. It somehow makes every technique "
            "feel a little easier to pull off, oil stains and all."
        ),
        "item_type": "armor",
        "wear_loc": "head",
        "cost_mission_points": 500,
        "stat_bonuses": {
            "max_chakra": 100,
            "intelligence": 5,
            "luck": 4,
            "damroll": 5,
        },
    },
    "tsunade's hokage necklace": {
        "vnum": 9757,
        "short_desc": "the First Hokage's Necklace",
        "long_desc": "A heavy crystal necklace on a beaded cord lies here, humming faintly with old chakra.",
        "description": (
            "A large, pale green crystal on a beaded cord, said to have once belonged to "
            "the very first Hokage before passing down to a legendary medical ninja whose "
            "bare fist could level stone. It carries an old, half-forgotten weight to it, "
            "as though it remembers far more than it lets on."
        ),
        "item_type": "armor",
        "wear_loc": "neck",
        "cost_mission_points": 500,
        "stat_bonuses": {
            "max_health": 150,
            "constitution": 6,
            "luck": 3,
        },
    },
    "shikamaru's flak jacket": {
        "vnum": 9758,
        "short_desc": "Shikamaru's Chunin Flak Jacket",
        "long_desc": "A dark green flak jacket lies here, its pockets clearly built for someone who plans ahead.",
        "description": (
            "A standard-issue Chunin flak jacket, worn by a famously lazy genius who "
            "always seemed three moves ahead of everyone else anyway. Wearing it seems "
            "to make every decision come a little easier, and every plan a little harder "
            "to see coming."
        ),
        "item_type": "armor",
        "wear_loc": "body",
        "cost_mission_points": 500,
        "stat_bonuses": {
            "wisdom": 6,
            "intelligence": 6,
            "armor_class": -12,
        },
    },
    "deidara's clay pouches": {
        "vnum": 96000,  # moved from 9759 (Section 133, per direct request): a genuine, real, pre-existing collision with the Alloy Ingot crafting material (content.py) -- legendary items register after materials, so this was silently overwriting Alloy Ingot's own template every server start. Confirmed directly: the legendary item moves, not the material. 96000 confirmed genuinely free via direct scan.
        "short_desc": "Deidara's Clay Pouches",
        "long_desc": "A pair of pouches lies here, faint traces of dried clay still clinging to the seams.",
        "description": (
            "A pair of weathered pouches, worn at the hip, still faintly dusted with dried "
            "clay from countless explosive creations. Worn by an artist convinced that "
            "true art is fleeting -- and willing to prove it, loudly, whenever given the "
            "chance."
        ),
        "item_type": "armor",
        "wear_loc": "waist",
        "cost_mission_points": 500,
        "stat_bonuses": {
            "damroll": 9,
            "dexterity": 5,
            "hitroll": 5,
            "armor_class": -6,
        },
    },
    "might guy's jumpsuit": {
        "vnum": 9760,
        "short_desc": "Might Guy's Green Jumpsuit",
        "long_desc": "A bright green jumpsuit lies here, radiating an almost tangible enthusiasm.",
        "description": (
            "A bright green, skin-tight jumpsuit, built for a taijutsu specialist who "
            "never once slowed down. Somehow it seems to make every step lighter and "
            "every stance more solid at the same time -- an odd combination that "
            "shouldn't work nearly as well as it does."
        ),
        "item_type": "armor",
        "wear_loc": "body",
        "cost_mission_points": 500,
        "stat_bonuses": {
            "strength": 6,
            "constitution": 4,
            "armor_class": -10,
        },
    },
    "rock lee's ankle weights": {
        "vnum": 9761,
        "short_desc": "Rock Lee's Ankle Weights",
        "long_desc": "A pair of heavy ankle weights lie here, orange straps faded from countless training sessions.",
        "description": (
            "A pair of genuinely heavy ankle weights with a familiar orange trim, worn "
            "threadbare from an almost absurd amount of daily training. Taking them off "
            "after wearing them long enough is said to feel like flying -- but simply "
            "wearing them at all is already a serious workout."
        ),
        "item_type": "armor",
        "wear_loc": "legs",
        "cost_mission_points": 500,
        "stat_bonuses": {
            "dexterity": 8,
            "strength": 4,
            "max_stamina": 100,
        },
    },
    "itachi's akatsuki ring": {
        "vnum": 9762,
        "short_desc": "Itachi's Akatsuki Ring",
        "long_desc": "A plain ring rests here, marked with a single kanji, its band scuffed from a black cloak's sleeve.",
        "description": (
            "A plain ring marked with a single kanji, once worn on the hand of a prodigy "
            "who carried a burden he never explained to anyone. There's a quiet, watchful "
            "stillness to it -- as though it's always paying closer attention than it "
            "lets on."
        ),
        "item_type": "armor",
        "wear_loc": "finger",
        "cost_mission_points": 500,
        "stat_bonuses": {
            "hitroll": 4,
            "damroll": 4,
            "intelligence": 4,
        },
    },
    "pain's piercings": {
        "vnum": 9763,
        "short_desc": "Pain's Facial Piercings",
        "long_desc": "A set of dark metal piercings lies here, arranged in a precise, unsettling pattern.",
        "description": (
            "A set of dark metal piercings, arranged with an almost ritual precision -- "
            "worn by a figure who spoke of pain, and peace, and paid for both in ways "
            "few others ever could. Wearing them leaves a faint, constant hum just "
            "beneath the skin."
        ),
        "item_type": "armor",
        "wear_loc": "piercing",
        "cost_mission_points": 500,
        "stat_bonuses": {
            "max_chakra": 150,
            "intelligence": 5,
            "damroll": 4,
            "armor_class": -8,
        },
    },
    "konan's paper flower": {
        "vnum": 9764,
        "short_desc": "Konan's Paper Flower",
        "long_desc": "A single paper flower lies here, folded with impossibly precise creases.",
        "description": (
            "A single paper flower, folded with impossibly precise creases and pinned "
            "neatly into the hair -- worn by a shinobi whose origami was as deadly as it "
            "was beautiful. It rustles faintly even in perfectly still air, as though "
            "waiting for a reason to move."
        ),
        "item_type": "armor",
        "wear_loc": "head",
        "cost_mission_points": 500,
        "stat_bonuses": {
            "dexterity": 6,
            "luck": 5,
            "wisdom": 3,
            "damroll": 4,
        },
    },
    "orochimaru's rope belt": {
        "vnum": 9765,
        "short_desc": "Orochimaru's Purple Rope Belt",
        "long_desc": "A length of dark purple rope lies here, cool to the touch no matter the weather.",
        "description": (
            "A long, dark purple rope worn as a belt, unnervingly cool to the touch no "
            "matter the weather -- worn by a rogue Sannin whose ambition and cruelty were "
            "matched only by his raw skill. Wearing it leaves a faint, unpleasant sense "
            "of being watched."
        ),
        "item_type": "armor",
        "wear_loc": "waist",
        "cost_mission_points": 500,
        "stat_bonuses": {
            "dexterity": 6,
            "intelligence": 6,
            "armor_class": -10,
        },
    },
    "neji's forehead bandages": {
        "vnum": 9766,
        "short_desc": "Neji's Forehead Bandages",
        "long_desc": "A neat wrap of white bandages lies here, worn in place of a forehead protector.",
        "description": (
            "A neat wrap of white bandages, worn across the forehead by a Hyuga prodigy "
            "who saw further and clearer than almost anyone else in his generation. "
            "Wearing it sharpens the senses -- as though the world had quietly come into "
            "clearer focus."
        ),
        "item_type": "armor",
        "wear_loc": "head",
        "cost_mission_points": 500,
        "stat_bonuses": {
            "armor_class": -15,
            "wisdom": 5,
            "luck": 3,
        },
    },
    "tobi's spiral mask": {
        "vnum": 9767,
        "short_desc": "Tobi's Orange Spiral Mask",
        "long_desc": "An orange mask lies here, a single spiral pattern swirling across its surface.",
        "description": (
            "A plain orange mask marked with a single swirling spiral, worn by a figure "
            "whose cheerful, clumsy act hid something far older and far more dangerous "
            "underneath. Wearing it leaves an odd, disorienting sense of being somewhere "
            "else entirely, just for a heartbeat."
        ),
        "item_type": "armor",
        "wear_loc": "head",
        "cost_mission_points": 500,
        "stat_bonuses": {
            "dexterity": 7,
            "armor_class": -15,
            "hitroll": 5,
        },
    },
    "kabuto's glasses": {
        "vnum": 9768,
        "short_desc": "Kabuto's Round Glasses",
        "long_desc": "A pair of round, wire-framed glasses lies here, lenses reflecting more light than they should.",
        "description": (
            "A pair of round, wire-framed glasses, worn by a spy and medical prodigy who "
            "always seemed to know more than he let on. Looking through them sharpens "
            "the eye for detail -- and for exactly where an opponent's next weakness is "
            "about to show."
        ),
        "item_type": "armor",
        "wear_loc": "head",
        "cost_mission_points": 500,
        "stat_bonuses": {
            "intelligence": 7,
            "wisdom": 4,
            "hitroll": 4,
        },
    },
    "killer b's sunglasses": {
        "vnum": 9769,
        "short_desc": "Killer B's Sunglasses",
        "long_desc": "A pair of dark sunglasses lies here, radiating an unmistakable sense of style.",
        "description": (
            "A pair of dark, stylish sunglasses worn by an eight-tailed jinchuriki with "
            "more confidence, more rhythm, and more raw power than almost anyone else "
            "around. Wearing them feels like picking up the beat of something much "
            "bigger than yourself."
        ),
        "item_type": "armor",
        "wear_loc": "head",
        "cost_mission_points": 500,
        "stat_bonuses": {
            "strength": 5,
            "max_chakra": 80,
            "luck": 3,
        },
    },
    "sakumo's white fang blade": {
        "vnum": 9770,
        "short_desc": "Sakumo's White Fang Chakra Blade",
        "long_desc": "A long white blade lies here, its edge worn smooth by a legendary reputation.",
        "description": (
            "A long, pale blade with a keen, worn edge -- once wielded by a shinobi so "
            "feared and respected in his prime that entire enemy villages retreated at "
            "the mere mention of his name. It moves almost too easily, as though eager "
            "to live up to that reputation all over again."
        ),
        "item_type": "weapon",
        "weapon_type": "sword",
        "wear_loc": "wielded",
        "cost_mission_points": 500,
        "stat_bonuses": {
            "hitroll": 10,
            "damroll": 12,
            "strength": 4,
        },
    },
}



# Gameplay stat enrichment keeps existing Nindo_mud bonuses unchanged,
# and adds modest combat-derived bonuses to a few thinner 500-MP items.
# We cannot verify source-game item numbers: these are original Nindo_mud
# balancing additions, not imported NarutoMUD stats. Added bonuses use
# hitroll/damroll/armor_class, which our engine derives from equipment
# on each evaluation, so they apply even to items ALREADY equipped without
# re-wearing or unsafe direct changes to saved player attributes.
#
# Character-inspired, item-specific xterm-256 presentation.
# These colors are Nindo_mud's ORIGINAL art direction. The other NarutoMUD
# does not publish verified ANSI item palettes, so don't misattribute these.
# Never embed these control codes into stored short_desc, inventory names, or
# builder-defined item prototypes. IDs are stable even if old item keys move.
# Quiet, readable character-themed colors for the Kage's mission-point shop.
# One-color entries use a single xterm-256 shade for the ENTIRE name.
# The six selected existing two-color designs intentionally keep their
# original word-by-word pattern. This affects rendered text ONLY, never
# stored names, world files, object templates, prices or stat bonuses.
LEGENDARY_COLOR_SCHEMES = {
    9751: (208,),       # Naruto - warm orange
    9752: (110,),       # Sasuke - muted Uchiha blue
    9753: (252, 117),   # Kakashi - KEEP original mask steel/lightning
    9754: (180,),       # Gaara - soft desert sand
    9755: (140,),       # Kankuro - dusky puppeteer purple
    9756: (167,),       # Jiraiya - muted crimson
    9757: (114,),       # Tsunade - jade-green crystal
    9758: (107,),       # Shikamaru - flak-jacket olive
    96000: (220, 255), # Deidara - KEEP original clay/gold
    9760: (77,),        # Might Guy - leaf green
    9761: (113,),       # Rock Lee - soft training green
    9762: (203, 245),  # Itachi - KEEP original red/steel ring
    9763: (141,),       # Pain - Rinnegan lavender
    9764: (153,),       # Konan - gentle paper blue
    9765: (139,),       # Orochimaru - muted serpent purple
    9766: (255, 117),  # Neji - KEEP original white/blue bandages
    9767: (208, 223),  # Tobi - KEEP original orange/sand mask
    9768: (189,),       # Kabuto - silvery glass
    9769: (179,),       # Killer B - warm muted gold
    9770: (255, 159),  # Sakumo - KEEP original White Fang/chakra blade
}


def styled_name(item_name: str):
    """Color a Kage legendary name without altering the persisted item ID.

    Most rewards use one coherent 256-color shade so Kage's shop stays
    readable. Six specifically preserved classics retain word-by-word
    dual-tone highlights. Unrelated items keep their existing visuals.
    """
    lookup = item_name.casefold()
    for data in LEGENDARY_ITEMS.values():
        if lookup != data["short_desc"].casefold():
            continue
        palette = LEGENDARY_COLOR_SCHEMES.get(data["vnum"])
        if palette is None:
            return None
        if len(palette) == 1:
            return f"&[{palette[0]}]{item_name}&x"
        return " ".join(
            f"&[{palette[index % len(palette)]}]{word}"
            for index, word in enumerate(item_name.split())
        ) + "&x"
    return None

def register_all(olc_module, combat_module) -> None:
    """Registers every legendary item as a real oset-style prototype
    in olc_module.OBJECT_TEMPLATES, called once from content.populate()
    at server start -- same pattern every other piece of shipped item
    content in this project already uses (see e.g. the scroll_jutsu
    registration nearby in content.py)."""
    for key, data in LEGENDARY_ITEMS.items():
        vnum = data["vnum"]
        proto = olc_module.default_object(vnum, data["short_desc"])
        proto["short_desc"] = data["short_desc"]
        proto["long_desc"] = data["long_desc"]
        proto["description"] = data["description"]
        proto["item_type"] = data["item_type"]
        proto["weapon_type"] = data.get("weapon_type", "")
        proto["wear_loc"] = data["wear_loc"]
        proto["rarity"] = "legendary"
        proto["keywords"] = data["short_desc"]
        proto["stat_bonuses"] = dict(data["stat_bonuses"])
        proto["extra_flags"] = []  # deliberately NOT no_sac -- a prior explicit request confirmed every item in the game must remain sacrificeable, no exceptions (see test_every_registered_item_can_be_sacrificed)
        olc_module.OBJECT_TEMPLATES[vnum] = proto


def find_by_query(query: str):
    """Reverse lookup by partial name match, matching the same
    substring-match convention used everywhere else in this project
    (see e.g. commands._find_mission's own keyword matching) --
    returns (key, data) or (None, None) if nothing matches."""
    query = query.lower()
    for key, data in LEGENDARY_ITEMS.items():
        if query in key or query in data["short_desc"].lower():
            return key, data
    return None, None
