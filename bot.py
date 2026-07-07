"""
Główny punkt wejścia bota-radia Discord + dashboard webowy.
Uruchomienie: python bot.py

Wymaga działającego serwera Lavalink (osobna usługa - patrz README.md /
folder lavalink/), do którego bot łączy się przez bibliotekę wavelink.
Dashboard webowy (FastAPI) startuje w tym samym procesie, na porcie z
env PORT (Railway ustawia go automatycznie).
"""
import asyncio
import time

import discord
import uvicorn
import wavelink
from discord.ext import commands, tasks

import config
from utils.database import Database
from utils.player import PlayerManager, MusicPlayer
from utils.http import close_session

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True


def _lavalink_connected() -> bool:
    return any(node.status is wavelink.NodeStatus.CONNECTED for node in wavelink.Pool.nodes.values())


class RadioBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.db = Database()
        self.players = PlayerManager(self)

    async def connect_lavalink(self) -> bool:
        if not config.LAVALINK_HOST:
            print("[lavalink] Brak LAVALINK_HOST w zmiennych środowiskowych - muzyka nie będzie działać.")
            return False
        if _lavalink_connected():
            return True
        scheme = "https" if config.LAVALINK_SECURE else "http"
        uri = f"{scheme}://{config.LAVALINK_HOST}:{config.LAVALINK_PORT}"
        node = wavelink.Node(uri=uri, password=config.LAVALINK_PASSWORD)
        try:
            await wavelink.Pool.connect(nodes=[node], client=self)
            return True
        except Exception as e:
            print(f"[lavalink] Nie udało się połączyć z serwerem Lavalink pod {uri}: {e}")
            return False

    async def setup_hook(self):
        await self.db.connect()
        for ext in ("cogs.music", "cogs.settings"):
            await self.load_extension(ext)
        await self.tree.sync()

        await self.connect_lavalink()
        self.autoplay_watchdog.start()

        # Dashboard webowy - w tym samym procesie/loopie co bot
        asyncio.create_task(self._start_dashboard())

    async def _start_dashboard(self):
        from web.app import app as fastapi_app
        fastapi_app.state.bot = self
        server_config = uvicorn.Config(
            fastapi_app, host="0.0.0.0", port=config.PORT, log_level="warning"
        )
        server = uvicorn.Server(server_config)
        print(f"[dashboard] Startuję na porcie {config.PORT}")
        await server.serve()

    async def on_ready(self):
        print(f"Zalogowano jako {self.user} (ID: {self.user.id})")
        await self._restore_radio()
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.listening, name="📻 radio"
        ))

    async def _restore_radio(self):
        """Po (re)starcie bota przywraca radio na serwerach, które je miały włączone."""
        guilds_cfg = await self.db.get_all_radio_guilds()
        for cfg in guilds_cfg:
            guild = self.get_guild(cfg["guild_id"])
            if guild is None:
                continue
            channel = guild.get_channel(cfg["voice_channel_id"])
            if channel is None:
                continue
            playlist = await self.db.get_playlist(cfg["guild_id"])
            if not playlist:
                continue
            try:
                player = await self.players.connect(channel)
                player.set_radio_tracks([t["url"] for t in playlist])
                await player.apply_eq_preset(cfg["eq_preset"])
                await player.set_volume(cfg["volume"])
                await player.start_if_idle()
                print(f"[radio] Przywrócono radio na serwerze {guild.name}")
            except Exception as e:
                print(f"[radio] Nie udało się przywrócić radia na {guild.name}: {e}")

    @tasks.loop(seconds=30)
    async def autoplay_watchdog(self):
        """Co 30s: sprawdza połączenie z Lavalink (wznawia je razie potrzeby),
        dogląda radio (dołącza ponownie po rozłączeniu) i wznawia granie po
        upływie tymczasowej pauzy (/stop na X minut)."""
        was_connected = _lavalink_connected()
        lavalink_ok = await self.connect_lavalink()

        for player in self.players.all():
            if player.paused_until and time.time() >= player.paused_until:
                player.paused_until = 0.0
                try:
                    await self.db.set_paused_until(player.guild.id, 0)
                except Exception:
                    pass
                await player.resume_now()
                continue
            if player.paused_until:
                continue  # nadal w trakcie tymczasowej pauzy
            if lavalink_ok and (not was_connected or (not player.playing and not player.paused)):
                if player.query_queue or player.radio_enabled:
                    await player.start_if_idle()

        guilds_cfg = await self.db.get_all_radio_guilds()
        for cfg in guilds_cfg:
            guild = self.get_guild(cfg["guild_id"])
            if guild is None or isinstance(guild.voice_client, MusicPlayer):
                continue
            channel = guild.get_channel(cfg["voice_channel_id"])
            if channel is None:
                continue
            playlist = await self.db.get_playlist(cfg["guild_id"])
            if not playlist:
                continue
            try:
                player = await self.players.connect(channel)
                player.set_radio_tracks([t["url"] for t in playlist])
                await player.apply_eq_preset(cfg["eq_preset"])
                await player.set_volume(cfg["volume"])
                await player.start_if_idle()
                print(f"[radio] Ponownie połączono z kanałem radia na {guild.name}")
            except Exception as e:
                print(f"[radio] Błąd ponownego łączenia na {guild.name}: {e}")

    @autoplay_watchdog.before_loop
    async def before_watchdog(self):
        await self.wait_until_ready()

    async def close(self):
        await self.db.close()
        await close_session()
        await super().close()


bot = RadioBot()


@bot.listen()
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
    print(f"[lavalink] Połączono z węzłem Lavalink: {payload.node.identifier}")


@bot.listen()
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    player = payload.player
    if player is not None and isinstance(player, MusicPlayer):
        await player.play_next()


@bot.listen()
async def on_wavelink_track_exception(payload: wavelink.TrackExceptionEventPayload):
    print(f"[lavalink] Błąd odtwarzania utworu: {payload.exception}")
    player = payload.player
    if player is not None and isinstance(player, MusicPlayer):
        await player.play_next()


@bot.listen()
async def on_wavelink_track_stuck(payload: wavelink.TrackStuckEventPayload):
    print(f"[lavalink] Utwór się zaciął, pomijam: {payload.track.title}")
    player = payload.player
    if player is not None and isinstance(player, MusicPlayer):
        await player.play_next()


def main():
    if not config.DISCORD_TOKEN:
        raise SystemExit(
            "Brak DISCORD_TOKEN. Ustaw go w pliku .env (lokalnie) albo w Variables na Railway."
        )
    bot.run(config.DISCORD_TOKEN)


if __name__ == "__main__":
    main()
