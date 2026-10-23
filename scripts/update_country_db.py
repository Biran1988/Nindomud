"""Download a monthly DB-IP Country Lite snapshot; run with the server stopped."""
import argparse
import datetime
import os
from pathlib import Path
import re
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import country_geo


def update(month):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise ValueError("Month must have YYYY-MM format.")
    url = f"https://download.db-ip.com/free/dbip-country-lite-{month}.csv.gz"
    with urllib.request.urlopen(url, timeout=60) as response:
        payload = response.read(32 * 1024 * 1024 + 1)
    if len(payload) > 32 * 1024 * 1024:
        raise ValueError("Country download exceeded the size limit.")
    tables = country_geo.parse_database(payload)
    if sum(len(t[0]) for t in tables.values()) < 100_000:
        raise ValueError("Incomplete country database; keeping the previous snapshot.")
    target = country_geo.DATABASE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=target.parent, prefix=".country-")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(f"Installed DB-IP Country Lite {month}. Restart the server and rebuild releases.")
    print("IP geolocation by DB-IP (https://db-ip.com), CC BY 4.0.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", default=datetime.date.today().strftime("%Y-%m"))
    update(parser.parse_args().month)
