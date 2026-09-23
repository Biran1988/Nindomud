"""
Profanity filter for character names (Section 59).

Checked as a SUBSTRING, not just an exact match (unlike
canon_names.py, where exact match is enough since canon names are
specific whole words) -- a name that embeds a blocked word inside a
longer one (e.g. tacking letters on the front or back) is still
blocked, since that's the obvious way someone would try to slip one
past an exact-match-only filter.

Deliberately a short, unambiguous list of clearly offensive terms and
slurs, not an attempt at a exhaustive obscenity dictionary -- the goal
is keeping character names from being slurs or overt profanity, not
policing every mild word someone might find in a name. A name that
happens to contain a common English word as a coincidental substring
(most names will, for short enough blocked terms) is an accepted
false-positive risk in exchange for not needing separate exact/
substring logic per word.
"""

BLOCKED_SUBSTRINGS = {
    "fuck", "shit", "cunt", "nigger", "nigga", "faggot", "fag", "retard",
    "whore", "bitch", "rape", "molest", "pedo", "nazi", "hitler",
}


def is_blocked(name: str) -> bool:
    lowered = name.lower()
    return any(word in lowered for word in BLOCKED_SUBSTRINGS)
