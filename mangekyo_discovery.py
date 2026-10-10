"""Persist which Mangekyo eye techniques a character has actually used."""

import data_jutsu


def roster_key(jutsu_key: str) -> str:
    jutsu = data_jutsu.JUTSU[jutsu_key]
    return jutsu.get("mangekyo_roster_key", jutsu_key)


def record_use(player, jutsu_key: str) -> None:
    key = roster_key(jutsu_key) if jutsu_key in data_jutsu.JUTSU else jutsu_key
    if key not in player.mangekyo_eyes_used:
        player.mangekyo_eyes_used.append(key)
        import storage
        storage.save_player(player)


def can_read(session, entry: dict) -> bool:
    key = entry["primary_keyword"].lower()
    if key in {"stab", "impale", "burn", "crush", "unmake"}:
        key = "tsukuyomi"
    jutsu = data_jutsu.JUTSU.get(key)
    if key != "izanagi" and (jutsu is None or jutsu.get("kkg_gate") != "mangekyo_technique"):
        return True
    if session.account is not None and session.account.staff_level != "player":
        return True
    player = session.player
    if not player or player.bloodline_id != "sharingan" or not player.bloodline_mangekyo:
        return False
    eye = roster_key(key) if jutsu else "izanagi"
    return (eye in (player.mangekyo_eye_1, player.mangekyo_eye_2)
            and eye in player.mangekyo_eyes_used)
