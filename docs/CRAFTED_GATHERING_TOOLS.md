# Bukijutsu blacksmith: gathering-tool tiers

Use `craft tool <rod|axe|pickaxe> <iron|steel|chakra>` or the shorthand
`craft rod iron`, `craft axe steel`, `craft pickaxe chakra`. The crafts require
**Bukijutsu ninja level 25+** (the general-class level-70 weapon and armor
crafting unlock does **not** apply). The blacksmith must carry the two items
listed below; each is consumed on successful completion of a 20-second craft.
There is no requirement to stand in an NPC shop.

| Tier | Required materials | Durability |
| --- | --- | ---: |
| Basic | Bought Kindling rod, Copper pickaxe, Copper axe | 250 uses |
| Ironbound Oak | Sturdy Oak Log + Iron Ingot | 400 uses |
| Steel Ironwood | Ironwood Log + Steel Ingot | 650 uses |
| Chakra Steel Heartwood | Ancient Heartwood Log + Chakra Steel Ingot | 1,000 uses |

Every upgraded tool retains the ability to gather **all lower-tier** resources.
The job's independent Fishing, Mining, or Lumberjack level must still meet the
item's level requirement. Higher-tier tools have slightly improved weighting
toward harder resources in the overlapping catch pools.

## Fishing rods

| Tier | Job level required to hold | Maximum fish newly reachable |
| --- | ---: | --- |
| Kindling | 1 | Minnow, Sardine, Trout (Fishing 15) |
| Ironbound Oak | 15 | Bass (Fishing 25), Salmon (Fishing 40) |
| Steel Ironwood | 40 | Swordfish (Fishing 55), Koi (Fishing 75) |
| Chakra Steel Heartwood | 75 | Leviathan (Fishing 90) |

## Mining pickaxes

| Tier | Mining level required to hold | Maximum minerals newly reachable |
| --- | ---: | --- |
| Copper | 1 | Iron Ore, Rough Quartz |
| Ironbound Oak | 15 | Steel Ore (Mining 20), Raw Sapphire (Mining 25) |
| Steel Ironwood | 35 | Chakra Steel Ore (Mining 50), Raw Ruby (Mining 55) |
| Chakra Steel Heartwood | 75 | Raw Diamond (Mining 80) |

## Lumberjack axes

| Tier | Lumberjack level required to hold | Maximum wood newly reachable |
| --- | ---: | --- |
| Copper | 1 | Kindling, Birch Branch, Sturdy Oak Log (Lumberjack 15) |
| Ironbound Oak | 15 | Ironwood Log (Lumberjack 35) |
| Steel Ironwood | 35 | Masterwork Oak (Lumberjack 60), Ancient Heartwood (Lumberjack 85) |
| Chakra Steel Heartwood | 75 | Yew Log (Lumberjack 95) |

### Crafting-chain safety

The Copper tools gather Sturdy Oak and Iron Ore. Ironbound tools gather Ironwood
and Steel Ore. Steel Ironwood tools gather Ancient Heartwood and Chakra Steel
Ore. Thus each tier can provide the next tier's ingredients through its ordinary
gathering loop once the appropriate job level is reached. Players must still
smelt Iron, Steel and Chakra Steel ores before blacksmithing.

## Deployment

`Nindo_mud.zip` contains the updated source and rebuilt `Nindo_mud` launcher,
plus helpfiles. It **does not** contain `data/`: extract over the existing
program folder while keeping saved accounts, player inventories, world state,
and administrator modifications intact. Never replace the live folder wholesale.

Run `python -m unittest test_crafted_gathering_tools` and the full
`python -m unittest discover -p 'test_*.py'` to verify the recipes and resource
pool overlap.
