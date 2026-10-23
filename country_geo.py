"""Offline IPv4/IPv6 country lookup. IP geolocation by DB-IP (db-ip.com).

DB-IP Country Lite is CC BY 4.0. See geoip/README.md for attribution,
accuracy limits and refresh instructions. No player IP is sent to a service.
"""
import bisect
import csv
import gzip
import io
import ipaddress
from pathlib import Path

from country_names import COUNTRIES, COUNTRY_ALIASES

DATABASE_PATH = Path(__file__).resolve().parent / "geoip" / "country.csv.gz"
BUNDLED_DATABASE = None  # injected by the generated single-file launcher
_tables = None


def address(value):
    """Canonical socket address, including IPv4-mapped IPv6 peers."""
    addr = ipaddress.ip_address(str(value).split("%", 1)[0])
    return addr.ipv4_mapped if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped else addr


def resolve_country(value):
    query = " ".join(value.casefold().replace("_", " ").split())
    if query.upper() in COUNTRIES:
        return query.upper()
    for code, name in COUNTRIES.items():
        if name.casefold() == query:
            return code
    if query in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[query]
    raise ValueError("Unknown country. Use a full country name or a two-letter code (AU, NG).")


def parse_database(payload):
    tables = {4: ([], [], []), 6: ([], [], [])}
    with gzip.open(io.BytesIO(payload), "rt", encoding="utf-8") as stream:
        for start, end, code in csv.reader(stream):
            first, last = ipaddress.ip_address(start), ipaddress.ip_address(end)
            starts, ends, codes = tables[first.version]
            if (first.version != last.version or int(first) > int(last)
                    or code not in COUNTRIES and code != "ZZ"
                    or ends and int(first) <= ends[-1]):
                raise ValueError("Invalid or overlapping country database range.")
            starts.append(int(first))
            ends.append(int(last))
            codes.append(code)
    if not all(tables[v][0] for v in (4, 6)):
        raise ValueError("Country database must include IPv4 and IPv6.")
    return tables


def load():
    global _tables
    if _tables is None:
        _tables = parse_database(BUNDLED_DATABASE if BUNDLED_DATABASE is not None
                                 else DATABASE_PATH.read_bytes())
    return _tables


def lookup(value):
    addr = address(value)
    if not addr.is_global:
        return None
    starts, ends, codes = load()[addr.version]
    pos = bisect.bisect_right(starts, int(addr)) - 1
    if pos >= 0 and int(addr) <= ends[pos] and codes[pos] != "ZZ":
        return codes[pos]
    return None


def label(code):
    return f"{COUNTRIES[code]} ({code})" if code in COUNTRIES else "Unknown / local"
