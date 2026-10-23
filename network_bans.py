"""Persistent socket-level bans and staff connection commands."""
import datetime
import ipaddress
import json
import logging
import os
from pathlib import Path
import tempfile

import config
import country_geo
import storage

LOG = logging.getLogger(__name__)
DENIED_MESSAGE = "Access denied: this connection is banned.\r\n"
USAGE = ("ban [list|status] | ban [ip] <address or CIDR> [reason] | "
         "ban country <country name or code> | ban remove [ip] <address or CIDR> | "
         "ban remove country <country name or code>")


def _path():
    return Path(storage.DATA_DIR) / "network_bans.json"


def network(value):
    if "/" not in value:
        return ipaddress.ip_network(country_geo.address(value))
    result = ipaddress.ip_network(value, strict=False)
    if result.version == 6 and result.network_address.ipv4_mapped:
        if result.prefixlen < 96:
            raise ValueError("Use an IPv4 subnet for an IPv4-mapped address.")
        return ipaddress.ip_network(f"{result.network_address.ipv4_mapped}/{result.prefixlen - 96}")
    return result


def load_rules():
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("rules"), list):
        raise ValueError("Invalid network ban file; restore data/network_bans.json before starting.")
    for rule in data["rules"]:
        if not isinstance(rule, dict) or rule.get("kind") not in {"ip", "country"}:
            raise ValueError("Invalid network ban rule.")
        if rule["kind"] == "ip":
            network(rule["value"])
        elif rule.get("value") not in country_geo.COUNTRIES:
            raise ValueError("Invalid country ban rule.")
    return data["rules"]


def save_rules(rules):
    """Replace atomically: never announce a ban that wasn't persisted."""
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".network_bans-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"version": 1, "rules": rules}, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def matches(rule, ip, country):
    if rule["kind"] == "country":
        return bool(country and rule["value"] == country)
    addr = country_geo.address(ip)
    subnet = network(rule["value"])
    return addr.version == subnet.version and addr in subnet


def blocked(ip, country, rules=None):
    return any(matches(rule, ip, country) for rule in (load_rules() if rules is None else rules))


def initialize():
    # Validate once before listening. A broken rules/database file must not
    # silently disable bans. Load country data off the live event loop path.
    load_rules()
    country_geo.load()


def cmd_ip(session, args):
    if not session.account or session.account.staff_level not in config.STAFF_LEVELS[1:]:
        session.send("Only immortals may view connection IP addresses.")
        return
    from session import ACTIVE_SESSIONS
    query = " ".join(args).casefold()
    rows = []
    for other in list(ACTIVE_SESSIONS):
        if other.state.name == "CLOSED":
            continue
        name = other.player.name if other.player else "[logging in]"
        ip = getattr(other, "connection_ip", None) or "Unknown"
        if query and query not in name.casefold() and query not in ip.casefold():
            continue
        rows.append(f"{name:<18} {ip:<39} {str(getattr(other, 'connection_port', '') or ''):<5} "
                    f"{country_geo.label(getattr(other, 'connection_country', None))} [{other.state.name}]")
    session.send("Player             IP address                              Port  Country [state]")
    session.send_paginated(rows or ["No matching connections."])
    session.send(f"{len(rows)} connection(s). IP geolocation by DB-IP (https://db-ip.com).")


def cmd_ban(session, args):
    if not session.account or session.account.staff_level not in {"administrator", "implementor"}:
        session.send("Only Administrators and Implementors may manage connection bans.")
        return
    if not args or args[0].casefold() in {"list", "status"}:
        try:
            rules = load_rules()
            country_geo.load()
        except (OSError, ValueError, KeyError) as error:
            session.send(f"Ban configuration error: {error}")
            return
        session.send("Connection bans (saved across reboots):")
        for rule in rules:
            value = country_geo.label(rule["value"]) if rule["kind"] == "country" else rule["value"]
            session.send(f"{rule['kind']}: {value} | by {rule.get('by', '?')} | "
                         f"{rule.get('created', '?')} | {rule.get('reason', '')}")
        session.send(f"{len(rules)} ban(s). Offline IPv4/IPv6 country database ready. "
                     "IP geolocation by DB-IP (https://db-ip.com).")
        session.send(USAGE)
        return
    words = list(args)
    remove = words[0].casefold() in {"remove", "delete", "unban"}
    if remove:
        words.pop(0)
    kind = "country" if words and words[0].casefold() == "country" else "ip"
    if words and words[0].casefold() in {"ip", "country"}:
        words.pop(0)
    if not words:
        session.send(USAGE)
        return
    try:
        value = (country_geo.resolve_country(" ".join(words)) if kind == "country"
                 else str(network(words[0])))
        if kind == "country" and not remove:
            country_geo.load()  # never accept a country ban without a working database
        rules = load_rules()
        existing = next((r for r in rules if r["kind"] == kind and r["value"] == value), None)
        rule = {"kind": kind, "value": value, "by": session.account.name,
                "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "reason": " ".join(words[1:])[:240] if kind == "ip" else ""}
        if remove:
            if existing is None:
                session.send("That ban is not listed.")
                return
            rules.remove(existing)
        else:
            if existing is not None:
                session.send("That ban already exists.")
                return
            if getattr(session, "connection_ip", None) and matches(
                    rule, session.connection_ip, getattr(session, "connection_country", None)):
                session.send("Refused: that ban would block your own connection. Use a narrower IP ban.")
                return
            rules.append(rule)
        save_rules(rules)
    except (OSError, ValueError, KeyError) as error:
        session.send(f"Ban not changed: {error}")
        return
    label = country_geo.label(value) if kind == "country" else value
    LOG.warning("Network ban %s by %s: %s %s", "removed" if remove else "added",
                session.account.name, kind, value)
    session.send(f"Ban {'removed' if remove else 'saved'}: {label}.")
    if not remove:
        from session import ACTIVE_SESSIONS
        count = 0
        for other in list(ACTIVE_SESSIONS):
            ip = getattr(other, "connection_ip", None)
            if ip and matches(rule, ip, getattr(other, "connection_country", None)):
                if other.player:
                    try:
                        storage.save_player(other.player)
                    except OSError:
                        # The policy is already durable: one failed character
                        # save must not leave other banned sessions connected.
                        LOG.exception("Could not save a player before ban disconnect")
                other.send(DENIED_MESSAGE.strip())
                other.request_close()
                count += 1
        session.send(f"Disconnected {count} matching connection(s). Future logins are blocked.")
