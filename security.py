"""
Password hashing and validation.

Uses PBKDF2-HMAC-SHA256 from the standard library so the whole codebase
stays dependency-free. Passwords are NEVER stored or logged in plain text,
and are never echoed back to staff (Section 32/33).
"""

import hashlib
import hmac
import os
from typing import Optional, Tuple

from config import MIN_PASSWORD_LENGTH, PBKDF2_ITERATIONS


def hash_password(password: str, salt_hex: Optional[str] = None) -> Tuple[str, str]:
    """Return (salt_hex, hash_hex). Generates a new random salt if none given."""
    salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    _, computed = hash_password(password, salt_hex)
    return hmac.compare_digest(computed, hash_hex)


def validate_new_password(password: str, character_name: str,
                           previous_hash: Optional[Tuple[str, str]] = None) -> Tuple[bool, str]:
    """
    Enforce Section 32 password rules. Returns (ok, reason_if_not_ok).
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if password.lower() == character_name.lower():
        return False, "Password cannot be the same as your character name."
    if previous_hash is not None:
        salt_hex, hash_hex = previous_hash
        if verify_password(password, salt_hex, hash_hex):
            return False, "You cannot reuse your previous password."
    return True, ""
