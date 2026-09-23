"""
Canon character name blocklist (Section 58).

This project is deliberately an alternate-timeline setting with
player-created ninja, not the canon characters or storyline (see the
project's own framing from day one). Since character names are single
alphabetic words (2-20 letters -- session.py's _handle_name), this
list only needs first names/aliases, not full "First Last" pairs.

Not exhaustive -- the Naruto manga/anime names hundreds of characters,
many quite minor, and trying to enumerate all of them would be both
impractical and pointless (a background character nobody would
recognize isn't worth blocking a legitimate player name over). This
covers the widely-recognizable main cast: the Konoha 11 and their
senseis, the Sannin, the five Kage lines, Akatsuki, and other major
named characters players would obviously reach for first.
"""

BLOCKED_NAMES = {
    # Team 7 and immediate circle
    "naruto", "sasuke", "sakura", "kakashi", "sai", "yamato", "obito", "rin", "minato", "kushina",
    # Konoha 11 (the rest) and their senseis
    "shikamaru", "choji", "ino", "shino", "kiba", "hinata", "neji", "tenten", "lee", "gai",
    "asuma", "kurenai", "konohamaru", "hanabi",
    # Sannin and other Konoha legends
    "tsunade", "jiraiya", "orochimaru", "hiruzen", "hashirama", "tobirama", "madara", "izuna",
    "danzo", "shizune", "ibiki", "anko", "iruka", "ebisu",
    # Sand
    "gaara", "temari", "kankuro", "chiyo", "ebizo", "rasa",
    # Mist
    "zabuza", "haku", "mei", "kisame", "suigetsu",
    # Stone
    "onoki", "kurotsuchi", "kitsuchi",
    # Cloud
    "killerbee", "bee", "yugito", "darui", "ay", "raikage",
    # Akatsuki
    "itachi", "deidara", "sasori", "konan", "nagato", "pain", "yahiko", "hidan", "kakuzu",
    "zetsu", "tobi",
    # Uchiha clan
    "fugaku", "mikoto", "shisui",
}


def is_blocked(name: str) -> bool:
    return name.lower() in BLOCKED_NAMES
