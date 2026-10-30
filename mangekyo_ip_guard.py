"""Anti-multibox protection for the Mangekyo betrayal awakening.

Compare only actual TCP peer IP addresses stored on the live sessions.
Do not compare public profile data or accept client-provided IP values.
"""
import ipaddress
import time

import storage

LOCK_SECONDS = 7 * 24 * 60 * 60


def connection_address(session):
    raw = getattr(session, "connection_ip", None)
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        value = ipaddress.ip_address(raw.strip())
    except ValueError:
        return None
    if isinstance(value, ipaddress.IPv6Address) and value.ipv4_mapped:
        return value.ipv4_mapped
    return value


def ip_comparison(attacker_session, victim_session):
    """True=same IP; False=different IP; None=at least one unknown."""
    a = connection_address(attacker_session)
    b = connection_address(victim_session)
    if a is None or b is None:
        return None
    return a == b


def suspend_awakener(attacker_session, now=None):
    """Persist an independent seven-day account suspension before logout.

    Raises if no account can be saved; never pretend a penalty succeeded.
    Does not ban the shared IP itself, which may host innocent players.
    """
    if not getattr(attacker_session, "account", None):
        raise ValueError("Awakening requires an authenticated account.")
    account = storage.load_account(attacker_session.account.name)
    if account is None:
        # In-memory authentications can be newer than the disk snapshot.
        account = attacker_session.account
    now = time.time() if now is None else now
    account.mangekyo_lock_until = max(
        getattr(account, "mangekyo_lock_until", 0.0), now + LOCK_SECONDS)
    storage.save_account(account)
    attacker_session.account.mangekyo_lock_until = account.mangekyo_lock_until
    return account.mangekyo_lock_until
