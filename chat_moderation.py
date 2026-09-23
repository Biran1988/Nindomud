"""
Chat moderation (Section 95): a profanity filter and spam detector for
say/ooc/village chat, per direct request:

"put in a swear word filter for ooc and other chats along with spam
protection if someone spams a channel over and over it will auto
silence them for 10 minutes"

Confirmed design across 2 follow-ups:
- The profanity filter auto-CENSORS a filtered word (replaced with
  asterisks matching its own length) rather than blocking the whole
  message outright -- the cleaned-up message still gets sent.
- Spam detection is purely RATE-based, not content-based -- 5
  messages within a 10-second window, regardless of whether they're
  the same message repeated or genuinely different text each time.
  Triggers a genuine 10-minute auto-silence, reusing the exact same
  Player.silenced_until mechanism 'silence' itself uses (Section 94)
  -- an auto-silence behaves identically to a staff-issued one from
  the target's own perspective, just triggered automatically rather
  than by a staff command.
- Both apply to exactly the 3 channels silence already covers
  (say/ooc/village chat), confirmed directly rather than extended
  broader.

The word list here is intentionally small and easily extended --
this is a moderation mechanism, not a definitive list; the actual
words matter far less than the censoring/spam mechanism working
correctly.
"""

import re
import time

FILTERED_WORDS = [
    "fuck", "shit", "bitch", "asshole", "bastard", "cunt", "dick", "piss",
]

SPAM_MESSAGE_THRESHOLD = 5
SPAM_WINDOW_SECONDS = 10.0
SPAM_SILENCE_SECONDS = 10 * 60  # confirmed design: "auto silence them for 10 minutes"


def censor(message: str) -> str:
    """Replaces any filtered word found in message with asterisks of
    the same length, case-insensitively, matching whole words only
    (so a filtered word doesn't accidentally match as a substring
    inside a longer, innocent word). Confirmed design: censors rather
    than blocking the message outright."""
    def _replace(match: "re.Match") -> str:
        return "*" * len(match.group(0))

    for word in FILTERED_WORDS:
        message = re.sub(rf"\b{re.escape(word)}\b", _replace, message, flags=re.IGNORECASE)
    return message


def record_and_check_spam(session) -> bool:
    """Records this message's timestamp and returns True if the
    session has now genuinely exceeded the spam threshold (confirmed
    design: 5 messages within 10 seconds, purely rate-based -- doesn't
    need to be the same message repeated). If the threshold is
    exceeded, this ALSO applies the real 10-minute auto-silence
    directly (reusing Player.silenced_until, the exact same field
    'silence' itself sets) and clears the tracker, so the same burst
    of messages can't immediately re-trigger a second silence the
    moment the first one is applied."""
    now = time.time()
    session.recent_chat_times = [t for t in session.recent_chat_times if now - t < SPAM_WINDOW_SECONDS]
    session.recent_chat_times.append(now)
    if len(session.recent_chat_times) > SPAM_MESSAGE_THRESHOLD:
        session.recent_chat_times = []
        session.player.silenced_until = now + SPAM_SILENCE_SECONDS
        return True
    return False
