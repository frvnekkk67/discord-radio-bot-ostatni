import random
import time

import wavelink

from utils.voice_status import (
    set_voice_channel_status,
    clear_voice_channel_status,
)


# ==========================
# EQUALIZER
# ==========================

EQ_PRESETS: dict[str, list[float]] = {

    "flat": [0.0] * 15,

    "bas": [
        0.6, 0.55, 0.5, 0.4, 0.3,
        0.15, 0, 0, 0, 0,
        0, 0, 0, 0, 0
    ],

    "bass+": [
        0.8, 0.75, 0.7, 0.55, 0.4,
        0.2, 0.05, 0, 0, 0,
        0, 0, 0, 0, 0
    ],

    "bass++": [
        1.0, 0.95, 0.85, 0.7, 0.5,
        0.3, 0.15, 0.05, 0,
        -0.05, -0.1, -0.1, -0.1,
        -0.1, -0.1
    ],

    "club": [
        0.75, 0.7, 0.65, 0.5, 0.35,
        0.2, 0.1, 0.05, 0.05,
        0.1, 0.1, 0.05, 0, 0, 0
    ],

    "edm": [
        0.9, 0.85, 0.8, 0.6, 0.4,
        0.25, 0.15, 0.1, 0.1,
        0.05, 0, -0.05, -0.05,
        -0.05, -0.05
    ],
}


# ==========================
# ERRORS
# ==========================

class LavalinkUnavailableError(Exception):
    pass



def _node_error(error: Exception):

    text = str(error).lower()

    return (
        isinstance(
            error,
            wavelink.exceptions.InvalidNodeException
        )
        or "no nodes" in text
        or "connected state" in text
        or "connection" in text
    )



# ==========================
# SEARCH
# ==========================

async def resolve_track(query: str):

    if query.startswith(
        ("http://", "https://")
    ):
        search_query = query

    else:
        # YouTube search
        search_query = f"ytsearch:{query}"


    try:

        results = await wavelink.Playable.search(
            search_query
        )


    except Exception as e:

        if _node_error(e):
            raise LavalinkUnavailableError from e

        print(
            f"[music] Search error: {e}"
        )

        return None



    if not results:
        return None



    if isinstance(results, wavelink.Playlist):

        if results.tracks:
            return results.tracks[0]

        return None



    return results[0]



async def resolve_playlist_queries(url: str):

    try:

        results = await wavelink.Playable.search(
            url
        )


    except Exception as e:

        if _node_error(e):
            raise LavalinkUnavailableError from e

        print(
            f"[music] Playlist error: {e}"
        )

        return []


    if isinstance(results, wavelink.Playlist):

        return [
            track.identifier
            for track in results.tracks
            if track.identifier
        ]


    if results:

        return [
            results[0].identifier
        ]


    return []



# ==========================
# FILTERS
# ==========================

def build_filters(name: str):

    bands = EQ_PRESETS.get(
        name,
        EQ_PRESETS["flat"]
    )


    filters = wavelink.Filters()


    filters.equalizer = [
        {
            "band": i,
            "gain": gain
        }
        for i, gain in enumerate(bands)
    ]


    return filters



# ==========================
# PLAYER
# ==========================

class MusicPlayer(wavelink.Player):


    def __init__(self, *args, **kwargs):

        super().__init__(
            *args,
            **kwargs
        )

        self.text_channel = None

        self.query_queue = []

        self.now_playing = None

        self.radio_enabled = False

        self.radio_tracks = []

        self.paused_until = 0

        self.eq_preset = "flat"



    def add_to_queue(self, query):

        self.query_queue.append(query)



    def add_many_to_queue(self, queries):

        self.query_queue.extend(
            queries
        )



    def clear_queue(self):

        self.query_queue.clear()



    async def start_if_idle(self):

        if self.paused_until > time.time():
            return


        if not self.playing and not self.paused:

            await self.play_next()



    async def play_next(self):

        if not self.query_queue:

            if self.radio_enabled and self.radio_tracks:

                tracks = list(
                    self.radio_tracks
                )

                random.shuffle(tracks)

                self.query_queue.extend(
                    tracks
                )

            else:

                self.now_playing = None
                return



        query = self.query_queue.pop(0)


        try:

            track = await resolve_track(query)

        except Exception as e:

            print(
                f"[music] Track error: {e}"
            )

            return



        if not track:

            await self.play_next()
            return



        self.now_playing = track


        if self.channel:

            try:

                await set_voice_channel_status(
                    self.channel.id,
                    f"🎵 {track.title}"
                )

            except Exception:
                pass



        await self.play(track)



    async def play_now(self, query):

        track = await resolve_track(
            query
        )


        if not track:

            return False



        if self.now_playing:

            self.query_queue.insert(
                0,
                self.now_playing.identifier
            )


        self.now_playing = track


        await self.play(
            track
        )


        return True



    async def skip(self):

        await self.stop()



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



    async def apply_eq_preset(self, preset):

        if preset not in EQ_PRESETS:

            preset = "flat"


        self.eq_preset = preset


        await self.set_filters(
            build_filters(
                preset
            )
        )



    def set_radio_tracks(self, tracks):

        self.radio_tracks = list(
            tracks
        )

        self.radio_enabled = bool(
            tracks
        )



    def disable_radio(self):

        self.radio_enabled = False



    async def leave(self):

        self.disable_radio()

        self.query_queue.clear()


        channel_id = (
            self.channel.id
            if self.channel
            else None
        )


        await self.disconnect()


        if channel_id:

            await clear_voice_channel_status(
                channel_id
            )



# ==========================
# MANAGER
# ==========================

class PlayerManager:


    def __init__(self, bot):

        self.bot = bot



    def get(self, guild_id):

        guild = self.bot.get_guild(
            guild_id
        )


        if guild and isinstance(
            guild.voice_client,
            MusicPlayer
        ):

            return guild.voice_client


        return None



    async def connect(self, channel):

        if not wavelink.Pool.nodes:

            raise LavalinkUnavailableError(
                "Brak Lavalink node"
            )


        guild = channel.guild


        if isinstance(
            guild.voice_client,
            MusicPlayer
        ):

            if guild.voice_client.channel.id != channel.id:

                await guild.voice_client.move_to(
                    channel
                )


            return guild.voice_client



        player = await channel.connect(
            cls=MusicPlayer,
            self_deaf=True
        )


        return player



    def all(self):

        return [
            vc
            for vc in self.bot.voice_clients
            if isinstance(
                vc,
                MusicPlayer
            )
        ]
