# Country database

IP geolocation by [DB-IP](https://db-ip.com). This package includes the
unmodified **DB-IP Country Lite, October 2026** CSV database, compressed as
`country.csv.gz`. Source:
https://download.db-ip.com/free/dbip-country-lite-2026-10.csv.gz

The database is licensed under [Creative Commons Attribution 4.0
International](https://creativecommons.org/licenses/by/4.0/).
DB-IP retains its database rights. Nindo_mud's lookup code and country names
are separate from the database. DB-IP attribution is also displayed by the
`ip` and `ban` commands.

Country lookup works offline for IPv4 and IPv6, with no API key or Python
dependencies. It identifies an IP's estimated country, not a player's
citizenship or actual physical location. VPNs, proxies, shared gateways and
database inaccuracies can change the result. Local/private and unknown IPs
display as `Unknown / local` and are not matched by country rules; explicit
IP/subnet bans still apply to them. Use `ip` to inspect what the MUD sees.
The server uses the TCP socket peer and does not trust forwarded client text.
If using a proxy, it will see that proxy's address.

Refresh monthly while the server is stopped:

```sh
python3 scripts/update_country_db.py --month 2026-11
```

The updater validates both address families and replaces the file atomically.
Restart after updating. Rebuild the release with `scripts/build_release.py`
to embed the new database into the portable single-file server too.
If the policy or database is missing/corrupt, startup fails explicitly rather
than silently disabling bans. If a policy becomes corrupt during runtime,
new connections are refused until it is repaired.

# Staff commands

`ip` (Helper and higher) lists every open connection, including login and
editor sessions, with player name, socket IP/port, country and session state.
`ip Naruto` or `ip 203.0.113` filters by player or address.

`ban` (Administrator and Implementor) lists all rules and usage. Examples:

```text
ban 203.0.113.25
ban ip 203.0.113.0/24 repeated abuse
ban ip 2001:db8::/48
ban country Australia
ban country Nigeria
ban country United Kingdom
ban country AU
ban remove 203.0.113.25
ban remove country Nigeria
```

Rules apply to all accounts on a matching IP, including staff and character
creation. Adding a rule disconnects matching sessions after saving their
characters and blocks connections before the greeting/login prompt. A rule
that would ban the issuing staff member's own connection is refused. Rules
are atomically saved to `data/network_bans.json`, which is never shipped in
release downloads, so installing updates preserves existing bans. Keep that
file with normal server backups. Removing a rule does not override another
matching IP, subnet or country rule. For offline recovery, stop the server,
back up the policy, remove the incorrect rule from its `rules` list and restart.
