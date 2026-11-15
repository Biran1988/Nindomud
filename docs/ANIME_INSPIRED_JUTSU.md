# Anime-inspired combat arts — original Nindo_mud techniques

These techniques borrow **combat concepts**, not actual named techniques, from Sword Art Online, Fairy Tail, Bleach, Dragon Ball, Demon Slayer, Jujutsu Kaisen, Attack on Titan, One Punch Man and My Hero Academia. They remain Naruto-world chakra, taijutsu, genjutsu and weapon techniques.

**Unlocks:** each primary class receives its own art automatically at levels 25, 50, 75 and 100 (with login catch-up). Cross-class teaching uses the preexisting scroll rules. Teacher first-practice gates remain intact. Ninjutsu and Genjutsu use `perform <technique> <target>`; Taijutsu and Bukijutsu use the technique's bare name. All moves honor standard PvP/PvE rules, global level-scaled damage and costs, and cooldowns.

| Class | Level | Original jutsu | Inspiration | Status (on landed hit) | Cooldown | Restriction |
|---|---:|---|---|---|---:|---|
| ninjutsu | 25 | Dragonfire Pulse | Fairy Tail dragon magic | burning 30% | 7s | fire nature |
| ninjutsu | 50 | Spirit Cannon | Dragon Ball focused ki | drained 30% | 9s | None |
| ninjutsu | 75 | Lightning Dragon Cascade | Fairy Tail lightning magic | paralyzed 22% | 12s | lightning nature |
| ninjutsu | 100 | Celestial Nova Sphere | Dragon Ball energy blasts | off_balance 35% | 17s | None |
| taijutsu | 25 | Flashstep Palm | Bleach high-speed movement | off_balance 35% | 6s | None |
| taijutsu | 50 | Breathing Rhythm Rush | Demon Slayer rhythmic breathing | bleeding 30% | 8s | None |
| taijutsu | 75 | Titanbreaker Fist | Attack on Titan and One Punch Man heavy impacts | weakened 35% | 12s | None |
| taijutsu | 100 | Meteor Drive Combo | My Hero Academia impact combinations | stunned 20% | 17s | None |
| genjutsu | 25 | Phantom Floor Maze | Sword Art Online dungeon floors | disoriented 60% | 7s | None |
| genjutsu | 50 | Mirrored Guild Hall | Fairy Tail illusion magic | confused 55% | 10s | None |
| genjutsu | 75 | Endless Void Stage | Jujutsu Kaisen domain illusions | blinded 45% | 14s | None |
| genjutsu | 100 | Refracted Memory Prison | Bleach hypnotic perception | frightened 55% | 19s | None |
| bukijutsu | 25 | Starstream Sword Dance | Sword Art Online rapid sword combos | bleeding 30% | 7s | sword weapon |
| bukijutsu | 50 | Moonfang Draw | Bleach sword drawing attacks | off_balance 35% | 9s | sword or exotic weapon |
| bukijutsu | 75 | Ember Breathing Cut | Demon Slayer breathing sword forms | burning 32% | 12s | sword weapon |
| bukijutsu | 100 | Comet Blade Finale | Sword Art Online high-speed sword finishers | stunned 22% | 18s | sword or exotic weapon |

The hit damage range is dynamically scaled from the common Nindo damage ladder; use `help <technique>` for the current values and requirements. These are not transformations or maintained toggles.
