"""
MusicPlayer - rozszerzenie wavelink.Player:

- kolejka muzyki
- radio z playlistą w kółko
- play now (natychmiastowe odtworzenie)
- automatyczna kontynuacja
- pauza czasowa
- equalizer Lavalink
- obsługa LavaSrc (Spotify/SoundCloud/YouTube Music)

Audio obsługuje Lavalink.
"""

import random
import time

import wavelink

from utils.voice_status import (
    set_voice_channel_status,
    clear_voice_channel_status,
)


EQ_PRESETS: dict[str, list[float]] = {
    "flat": [0.0] * 15,

    "bas": [
        0.6, 0.55, 0.5, 0.4, 0.3,
        0.15, 0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0, 0.0
    ],

    "bass+": [
        0.8, 0.75, 0.7, 0.55, 0.4,
        0.2, 0.05, 0, 0, 0,
        0, 0, 0, 0, 0
    ],

    "bass++": [
        1.0, 0.95, 0.85, 0.7, 0.5,
        0.3, 0.15, 0.05, 0,
        -0.05, -0.1, -0.1, -0.1, -0.1, -0.1
    ],

    "club": [
        0.75, 0.7, 0.65, 0.5, 0.35,
        0.2, 0.1, 0.05, 0.05,
        0.1, 0.1, 0.05, 0, 0, 0
    ],
}


class LavalinkUnavailableError(Exception):
    pass


def _node_error(error: Exception):
    text = str(error).lower()

    return (
        isinstance(error, wavelink.exceptions.InvalidNodeException)
        or "no nodes" in text
        or "connected state" in text
    )


async def resolve_track(query: str):

    # URL Spotify / YouTube / SoundCloud zostaje bez zmian
    if query.startswith(("http://", "https://")):
        search = query

    else:
        # LavaSrc + YouTube Music
        search = f"scsearch:{query}"

    try:
        results = await wavelink.Playable.search(search)

    except Exception as e:
        if _node_error(e):
            raise LavalinkUnavailableError from e

        print(
            f"[music] Błąd wyszukiwania '{query}': {e}"
        )
        return None


    if not results:
        return None


    if isinstance(results, wavelink.Playlist):
        return (
            results.tracks[0]
            if results.tracks
            else None
        )


    return results[0]


def build_filters(name: str):

    bands = EQ_PRESETS.get(
        name,
        EQ_PRESETS["flat"]
    )

    filters = wavelink.Filters()

    filters.equalizer.set(
        bands=[
            {
                "band": i,
                "gain": gain
            }
            for i, gain in enumerate(bands)
        ]
    )

    return filters



class MusicPlayer(wavelink.Player):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.text_channel = None

        self.query_queue: list[str] = []

        self.now_playing = None

        self.radio_enabled = False
        self.radio_tracks = []

        self.paused_until = 0

        self.eq_preset = "flat"



    # ---------- QUEUE ----------


    def add_to_queue(self, query):

        self.query_queue.append(query)


    def add_many_to_queue(self, queries):

        self.query_queue.extend(queries)


    def clear_queue(self):

        self.query_queue.clear()



    async def start_if_idle(self):

        if self.paused_until > time.time():
            return

        if not self.playing and not self.paused:
            await self.play_next()



    async def play_next(self):

        if self.paused_until > time.time():
            return


        if not self.query_queue:

            if self.radio_enabled:

                tracks = list(self.radio_tracks)

                random.shuffle(tracks)

                self.query_queue.extend(tracks)

            else:

                self.now_playing = None

                if self.channel:
                    await clear_voice_channel_status(
                        self.channel.id
                    )

                return



        query = self.query_queue.pop(0)


        try:

            track = await resolve_track(query)


        except LavalinkUnavailableError:

            self.query_queue.insert(
                0,
                query
            )

            return



        if not track:

            await self.play_next()

            return



        self.now_playing = track


        if self.channel:

            await set_voice_channel_status(
                self.channel.id,
                f"🎵 {track.title}"
            )


        await self.play(track)



    async def play_now(self, query):

        track = await resolve_track(query)


        if not track:
            return False


        if self.now_playing:

            self.query_queue.insert(
                0,
                self.now_playing.uri
            )


        self.now_playing = track


        await self.play(track)


        return True



    async def skip(self):

        await self.stop()



    # ---------- PAUSE ----------


    async def pause_for(self, minutes):

        self.paused_until = (
            time.time()
            + minutes * 60
        )

        if self.playing:
            await self.pause(True)



    async def resume_now(self):

        self.paused_until = 0

        if self.paused:
            await self.pause(False)

        else:
            await self.start_if_idle()



    # ---------- EQ ----------


    async def apply_eq_preset(self, preset):

        if preset not in EQ_PRESETS:
            preset = "flat"

        self.eq_preset = preset

        await self.set_filters(
            build_filters(preset)
        )



    # ---------- RADIO ----------


    def set_radio_tracks(self, tracks):

        self.radio_tracks = list(tracks)

        self.radio_enabled = bool(tracks)



    def disable_radio(self):

        self.radio_enabled = False



    # ---------- LEAVE ----------


    async def leave(self):

        self.disable_radio()

        self.query_queue.clear()

        channel = (
            self.channel.id
            if self.channel
            else None
        )


        await self.disconnect()


        if channel:
            await clear_voice_channel_status(
                channel
            )




class PlayerManager:


    def __init__(self, bot):

        self.bot = bot



    def get(self, guild_id):

        guild = self.bot.get_guild(guild_id)

        if guild and isinstance(
            guild.voice_client,
            MusicPlayer
        ):
            return guild.voice_client

        return None



    async def connect(self, channel):

        guild = channel.guild


        if isinstance(
            guild.voice_client,
            MusicPlayer
        ):

            if guild.voice_client.channel.id != channel.id:
                await guild.voice_client.move_to(channel)


            return guild.voice_client



        return await channel.connect(
            cls=MusicPlayer,
            self_deaf=True
        )



    def all(self):

        return [
            vc
            for vc in self.bot.voice_clients
            if isinstance(vc, MusicPlayer)
        ]
