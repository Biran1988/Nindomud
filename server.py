"""
Asyncio TCP server. Wires each incoming connection to a Session, and runs
the pulse loop that drives automatic combat, mob respawns, and natural
regeneration.
"""

import asyncio
import socket

import config
import consumables
import storage
from session import ACTIVE_SESSIONS, Session

PULSE_SECONDS = 1.0  # ROM-style short pulse -- drives every periodic system's own elapsed-time counter below.
COMBAT_ROUND_SECONDS = 2.5  # a combat round used to fire every single pulse (1s) -- slowed per explicit request ("a little slower, each round is very fast").


def _enable_tcp_keepalive(writer: asyncio.StreamWriter) -> None:
    """Without this, a genuinely abrupt disconnect (linkdead -- no
    clean TCP close) is invisible to the connection loop below:
    reader.readline() just hangs forever waiting for data that will
    never arrive, so the session is never cleaned up on its own unless
    the same player reconnects (see Session._enter_world's kick-the-
    stale-session check). Enabling keepalive makes the OS actively
    probe an idle connection and eventually raise an error if it's
    truly dead, bounding how long a linkdead session can linger even
    if the player never comes back. Linux-specific tuning (TCP_KEEPIDLE
    etc.) is guarded since it isn't available on all platforms; the
    base SO_KEEPALIVE still applies everywhere."""
    try:
        sock = writer.get_extra_info("socket")
        if sock is None:
            return
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if hasattr(socket, "TCP_KEEPIDLE"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 15)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 4)
    except OSError:
        pass  # best-effort -- never let keepalive setup crash a connection


async def handle_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    def send_raw(text: str) -> None:
        try:
            writer.write(text.encode("utf-8", errors="ignore"))
        except Exception:
            pass

    def close_callback() -> None:
        try:
            writer.close()
        except Exception:
            pass

    session = Session(send_raw, close_callback)
    _enable_tcp_keepalive(writer)

    try:
        while True:
            data = await reader.readline()
            if not data:
                break
            line = data.decode("utf-8", errors="ignore")
            session.handle_line(line)
            if session.state.name == "CLOSED":
                break
    except (ConnectionResetError, asyncio.IncompleteReadError):
        pass
    finally:
        if session in ACTIVE_SESSIONS:
            ACTIVE_SESSIONS.remove(session)
        try:
            writer.close()
        except Exception:
            pass


async def pulse_loop() -> None:
    """Drives automatic combat rounds, mob respawns, natural regen,
    corpse decay, and periodic autosave."""
    import combat
    import corpses
    import programs
    import regen
    import storage
    import weather
    import auction
    import areas
    import territory
    import tips
    from session import ACTIVE_SESSIONS, State

    elapsed_since_regen = 0.0
    elapsed_since_idle_upkeep = 0.0
    elapsed_since_autosave = 0.0
    elapsed_since_weather = 0.0
    elapsed_since_time_of_day = 0.0
    elapsed_since_territory_income = 0.0
    elapsed_since_combat = 0.0
    elapsed_since_tips = 0.0
    tips_rotation_index = 0
    elapsed_since_area_reset = 0.0

    def _broadcast_all(message: str) -> None:
        for s in ACTIVE_SESSIONS:
            if s.state == State.PLAYING:
                s.send(message)
                s.send_prompt()

    while True:
        await asyncio.sleep(PULSE_SECONDS)
        elapsed_since_regen += PULSE_SECONDS
        elapsed_since_idle_upkeep += PULSE_SECONDS
        elapsed_since_autosave += PULSE_SECONDS
        elapsed_since_weather += PULSE_SECONDS
        elapsed_since_time_of_day += PULSE_SECONDS
        elapsed_since_territory_income += PULSE_SECONDS
        elapsed_since_combat += PULSE_SECONDS
        elapsed_since_tips += PULSE_SECONDS
        elapsed_since_area_reset += PULSE_SECONDS

        combat.process_respawns()
        corpses.process_decay()
        auction.process_expired_auctions()
        combat.process_wander()
        import tailed_beasts
        import world as world_module
        import session as session_module
        tailed_beasts.process_tailed_beasts(combat, world_module, session_module)
        tailed_beasts.process_rampages(combat, session_module)
        import mangekyo
        mangekyo.process_amaterasu_room_fires(combat, world_module)
        mangekyo.process_amaterasu_player_burns(combat, session_module)
        mangekyo.process_kamui_pocket_dimensions(combat, world_module, session_module)
        mangekyo.process_kekkei_no_me(combat, world_module, session_module)
        programs.process_random_triggers()
        territory.ensure_war_window_scheduled(_broadcast_all)
        territory.tick_captures(_broadcast_all)

        if elapsed_since_territory_income >= territory.INCOME_TICK_SECONDS:
            elapsed_since_territory_income = 0.0
            territory.tick_income()

        if elapsed_since_weather >= weather.WEATHER_CHANGE_INTERVAL_SECONDS:
            elapsed_since_weather = 0.0
            weather.tick_weather()

        if elapsed_since_time_of_day >= weather.DAY_NIGHT_INTERVAL_SECONDS:
            elapsed_since_time_of_day = 0.0
            weather.tick_time_of_day()

        # Status effects tick down every pulse for everyone, independent of
        # combat state -- this used to only happen inside resolve_pulse()
        # (i.e. only while actively fighting), which left effects frozen
        # outside combat or after the fight that applied them ended.
        combat.tick_all_mob_effects()
        combat.tick_pending_casts()
        for session in list(ACTIVE_SESSIONS):
            if session.state == State.PLAYING:
                combat.tick_effects_pulse(session)
                # Shadow Clone upkeep, per direct follow-up request
                # ("Clones can be summoned before combat and persist
                # until unsigned or chakra runs out") -- same
                # always-ticks-regardless-of-combat-state reasoning
                # as tick_effects_pulse just above.
                for message in combat.tick_shadow_clone_upkeep(session.player):
                    session.send(message)
                import tracking
                tracking.tick_tracking(session)

        if elapsed_since_combat >= COMBAT_ROUND_SECONDS:
            elapsed_since_combat = 0.0
            for session in list(ACTIVE_SESSIONS):
                if session.state == State.PLAYING and session.combat_target is not None:
                    combat.resolve_pulse(session)
                    session.send_prompt()
                if session.state == State.PLAYING and session.pvp_target is not None:
                    combat.resolve_pvp_pulse(session)
                    session.send_prompt()

        for session in list(ACTIVE_SESSIONS):
            if session.state == State.PLAYING and session.pending_action is not None:
                session.process_pending_action()
            if session.state == State.PLAYING:
                session.player.total_play_seconds += PULSE_SECONDS
                restored = consumables.tick_medical_healing(session.player)
                if restored:
                    session.send("Medicine restores " + ", ".join(f"{amount} {resource}" for resource, amount in restored.items()) + ".")
                    session.send_prompt()

        if elapsed_since_regen >= config.REGEN_INTERVAL_SECONDS:
            elapsed_since_regen -= config.REGEN_INTERVAL_SECONDS
            for session in list(ACTIVE_SESSIONS):
                if session.state == State.PLAYING and session.combat_target is None and session.pvp_target is None:
                    messages = regen.tick_player(session.player)
                    if messages:
                        for message in messages:
                            session.send(message)
                        session.send_prompt()

        if elapsed_since_idle_upkeep >= config.IDLE_SHARINGAN_UPKEEP_INTERVAL_SECONDS:
            elapsed_since_idle_upkeep -= config.IDLE_SHARINGAN_UPKEEP_INTERVAL_SECONDS
            for session in list(ACTIVE_SESSIONS):
                if session.state == State.PLAYING and session.combat_target is None and session.pvp_target is None:
                    for message in regen.tick_sharingan_idle(session.player):
                        session.send(message)
                        session.send_prompt()

        if elapsed_since_autosave >= config.AUTOSAVE_INTERVAL_SECONDS:
            elapsed_since_autosave = 0.0
            for session in list(ACTIVE_SESSIONS):
                if session.state == State.PLAYING:
                    storage.save_player(session.player)

        if elapsed_since_tips >= tips.TIPS_INTERVAL_SECONDS:
            elapsed_since_tips = 0.0
            tip_text, tips_rotation_index = tips.next_tip(tips_rotation_index)
            if tip_text is not None:
                for session in list(ACTIVE_SESSIONS):
                    if session.state == State.PLAYING and session.player.tips:
                        session.send(f"&C[Tip]&x {tip_text}")
                        session.send_prompt()

        if elapsed_since_area_reset >= areas.AREA_RESET_INTERVAL_SECONDS:
            elapsed_since_area_reset = 0.0
            areas.perform_all_area_resets()


async def run_server(host: str = config.HOST, port: int = config.PORT) -> None:
    storage.ensure_dirs()
    server = await asyncio.start_server(handle_connection, host, port)
    asyncio.create_task(pulse_loop())
    addr = server.sockets[0].getsockname()
    print(f"{config.MUD_NAME} MUD listening on {addr[0]}:{addr[1]}")
    async with server:
        await server.serve_forever()
