# October 30 gameplay delivery audit

This is a **source-code feature audit**, not just a renamed archive. The
standard release includes the full Python sources, a newly generated `Nindo_mud`
launcher with the same embedded sources, and in-game help files.

## In this release

- `teach <player> <skill>`: same primary class, mastered teacher (100%+),
  student already unlocked at <=5%; grants 45% without using a practice point
  and satisfies the first-lesson gate.
- Six summoning families including Salamander; level-250 progressions, with the
  Seven Ninja Hounds as the highest Ninken tier.
- Summon orders: `follow me`, `stay`, `guard`, `sleep`, `wake`, `rest`, `sit`,
  `stand`, `attack`, `assist`, `stop`, `status` and `help`.
- The Toad Stomach and Great Toad Stomach are **barriers**, not visible mob
  creatures. Target hostile NPCs via `summon toad stomach <enemy>` (level 90)
  or `summon toad <enemy>` (at level 250). The barrier traps its target,
  prevents ordinary NPC wandering, digests with each combat pulse, and
  ends when dismissed, the target is gone, or chakra upkeep fails.
- Chuunin Exam: Heaven and Earth scrolls count whether loose or in a backpack;
  the two scrolls are consumed before the stronger, different-class final 1v1.
  Leaving forfeits the exam; the final fight blocks normal exits.
- Bijuu: independent reserve, bond/control/mastery, chakra draw, cloaks, tails,
  cooperative sharing, avatar and a chakra-funded self-heal.
- Summoning contracts cannot be signed without a living Summon Elder.
- Updates already present in this branch remain in place, including closing
  Kamui from outside, Hyuuga progression, immortal spy, Izanami, Amaterasu
  suppression and other prior mechanics.

## Deployment safety

This ZIP intentionally **does not contain `data/`**. Extract into the existing
program directory while preserving `data/`; do not delete or replace the
installation directory. Back up live data before applying updates.

## Regression tests

Run `python -m unittest discover -p 'test_*.py'` from the source directory.
The targeted `test_october30_delivery.py` checks teaching, scrolls in bags,
summon contracts, and the non-mob Toad Stomach barrier. The full unit suite is
also run before release. The large legacy `test_smoke.py` remains a separate
integration script and must be reported honestly if it fails.
