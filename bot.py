"""
Główny punkt wejścia bota-radia Discord + dashboard webowy.

Uruchomienie:
python bot.py
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



def _lavalink_connected():

    return any(
        node.status is wavelink.NodeStatus.CONNECTED
        for node in wavelink.Pool.nodes.values()
    )



class RadioBot(commands.Bot):

    def __init__(self):

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

        self.db = Database()
        self.players = PlayerManager(self)



    async def connect_lavalink(self):

        if not config.LAVALINK_HOST:

            print(
                "[lavalink] Brak hosta Lavalink"
            )

            return False



        if _lavalink_connected():

            return True



        scheme = (
            "https"
            if config.LAVALINK_SECURE
            else "http"
        )


        uri = (
            f"{scheme}://"
            f"{config.LAVALINK_HOST}:"
            f"{config.LAVALINK_PORT}"
        )


        try:

            node = wavelink.Node(
                uri=uri,
                password=config.LAVALINK_PASSWORD,
                identifier="main"
            )


            await wavelink.Pool.connect(
                nodes=[node],
                client=self
            )


            print(
                "[lavalink] Próba połączenia..."
            )


            return True



        except Exception as e:

            print(
                f"[lavalink] Błąd połączenia: {e}"
            )

            return False




    async def setup_hook(self):

        await self.db.connect()



        for ext in (
            "cogs.music",
            "cogs.settings"
        ):

            try:

                await self.load_extension(ext)

            except Exception as e:

                print(
                    f"[cog] Błąd {ext}: {e}"
                )



        await self.tree.sync()



        self.autoplay_watchdog.start()



        asyncio.create_task(
            self._start_dashboard()
        )




    async def _start_dashboard(self):

        from web.app import app as fastapi_app


        fastapi_app.state.bot = self



        server_config = uvicorn.Config(
            fastapi_app,
            host="0.0.0.0",
            port=config.PORT,
            log_level="warning"
        )


        server = uvicorn.Server(
            server_config
        )


        print(
            f"[dashboard] Start na porcie {config.PORT}"
        )


        await server.serve()




    async def on_ready(self):

        print(
            f"Zalogowano jako {self.user} "
            f"(ID: {self.user.id})"
        )


        await self.connect_lavalink()



        await self._restore_radio()



        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="📻 radio"
            )
        )




    async def _restore_radio(self):

        try:

            guilds_cfg = await self.db.get_all_radio_guilds()


            for cfg in guilds_cfg:

                guild = self.get_guild(
                    cfg["guild_id"]
                )


                if not guild:
                    continue


                channel = guild.get_channel(
                    cfg["voice_channel_id"]
                )


                if not channel:
                    continue



                playlist = await self.db.get_playlist(
                    cfg["guild_id"]
                )


                if not playlist:
                    continue



                player = await self.players.connect(
                    channel
                )


                player.set_radio_tracks(
                    [
                        x["url"]
                        for x in playlist
                    ]
                )


                await player.apply_eq_preset(
                    cfg["eq_preset"]
                )


                await player.set_volume(
                    cfg["volume"]
                )


                await player.start_if_idle()



        except Exception as e:

            print(
                f"[radio] Restore error: {e}"
            )




    @tasks.loop(seconds=120)
    async def autoplay_watchdog(self):

        try:

            lavalink_ok = await self.connect_lavalink()



            if not lavalink_ok:
                return



            for player in self.players.all():

                if (
                    player.paused_until
                    and time.time() >= player.paused_until
                ):

                    player.paused_until = 0

                    await player.resume_now()

                    continue



                if (
                    not player.playing
                    and not player.paused
                ):

                    if (
                        player.query_queue
                        or player.radio_enabled
                    ):

                        await player.start_if_idle()



        except Exception as e:

            print(
                f"[watchdog] {e}"
            )




    @autoplay_watchdog.before_loop
    async def before_watchdog(self):

        await self.wait_until_ready()




    async def close(self):

        await self.db.close()

        await close_session()

        await super().close()





bot = RadioBot()




@bot.listen()
async def on_wavelink_node_ready(
    payload: wavelink.NodeReadyEventPayload
):

    print(
        f"[lavalink] Gotowy: {payload.node.identifier}"
    )




@bot.listen()
async def on_wavelink_track_end(
    payload: wavelink.TrackEndEventPayload
):

    player = payload.player


    if isinstance(
        player,
        MusicPlayer
    ):

        await player.play_next()




@bot.listen()
async def on_wavelink_track_exception(
    payload: wavelink.TrackExceptionEventPayload
):

    print(
        f"[lavalink] Track error: {payload.exception}"
    )


    player = payload.player


    if isinstance(
        player,
        MusicPlayer
    ):

        await asyncio.sleep(2)

        await player.play_next()




@bot.listen()
async def on_wavelink_track_stuck(
    payload: wavelink.TrackStuckEventPayload
):

    print(
        "[lavalink] Track stuck"
    )


    player = payload.player


    if isinstance(
        player,
        MusicPlayer
    ):

        await player.play_next()




def main():

    if not config.DISCORD_TOKEN:

        raise SystemExit(
            "Brak DISCORD_TOKEN"
        )



    bot.run(
        config.DISCORD_TOKEN
    )




if __name__ == "__main__":

    main()
