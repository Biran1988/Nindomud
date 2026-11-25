"""Server-side village-entry gate. Never advertise access codes in-game."""

import hashlib
import hmac

# Fixed access-code verifier, not the plaintext code. This is a lightweight
# gameplay access restriction, not a substitute for account authentication.
_WH_SALT = b"nindomud:whirlpool:chargen:2026:v1"
_WH_DIGEST = "8c3af6d44b094702eb97eb7da48acc7e1ec29dc027639ebaf2df9194005afec3"


def verify_whirlpool_access_code(value: str) -> bool:
    """Compare without echoing, recording or returning the submitted code."""
    candidate = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), _WH_SALT, 200_000)
    return hmac.compare_digest(candidate, bytes.fromhex(_WH_DIGEST))


def verify_hidden_village_access_code(village: str, value: str) -> bool:
    """Use the existing gate unless staff supplies an independent server-only code."""
    import os
    from data_villages import VILLAGES
    if not VILLAGES.get(village, {}).get("hidden_at_creation"):
        return False
    if village == "whirlpool":
        return verify_whirlpool_access_code(value)
    configured = os.environ.get("NINDO_VILLAGE_ACCESS_" + village.upper())
    if configured is not None:
        return bool(configured and configured.casefold() != "cancel" and
                    hmac.compare_digest(value.encode("utf-8"), configured.encode("utf-8")))
    return verify_whirlpool_access_code(value)
