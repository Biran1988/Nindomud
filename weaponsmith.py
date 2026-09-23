"""
Weaponsmith (Section 63c) -- a crafting-only job on jobs.py's
framework: no gathering command of its own.

Per explicit request ("going in a different direction with crafting
... remove all current crafting recipes ... this is part of an
overall revamp of how crafting will work"), every recipe previously
registered here has been removed. The job itself still exists (see
jobs.JOB_NAMES, and it still contributes to a player's Max Chakra
bonus per level -- see jobs.JOB_STAT_BONUS) -- there's simply nothing
craftable through it right now, pending the new crafting system this
removal is making room for.
"""
