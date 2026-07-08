"""
MusicPlayer - rozszerzenie wavelink.Player o:
 - stałą playlistę radiową graną w kółko (losowa kolejność)
 - "zagraj teraz" - odtwarza wybrany utwór natychmiast, z pominięciem
   kolejki, a po jego zakończeniu wraca do normalnego grania
 - tymczasową pauzę na X minut (z automatycznym wznowieniem)
 - equalizer (presety filtrów Lavalink)

Faktyczne wyszukiwanie/streamowanie audio robi serwer Lavalink (przez
bibliotekę wavelink) - obsługuje zarówno bezpośrednie linki do plików
audio (http/https), jak i linki YouTube.
"""
import asyncio
import random
import re
import time

import wavelink

from utils.voice_status import set_voice_channel_status, clear_voice_channel_status

# Częsty błąd: link skopiowany z widoku pliku na GitHubie (strona HTML z
# podglądem), zamiast bezpośredniego linku do pliku. Naprawiamy to automatycznie.
_GITHUB_BLOB_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$")


def normalize_audio_url(url: str) -> str:
    match = _GITHUB_BLOB_RE.match(url.strip())
    if match:
        user, repo, branch, path = match.groups()
        return f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}"
    return url

# ---------- Equalizer: presety 15-pasmowego equalizera Lavalink ----------
# Każde pasmo to wzmocnienie w zakresie -0.25 (cisza) do 1.0 (podwojenie).
EQ_PRESETS: dict[str, list[float]] = {
    "flat": [0.0] * 15,

    "bas": [
        0.6, 0.55, 0.5, 0.4, 0.3,
        0.15, 0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0, 0.0
    ],

    "bass+": [
        0.8, 0.75, 0.7, 0.55, 0.4,
        0.25, 0.1, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0, 0.0
    ],

    "bass++": [
        1.0, 1.0, 0.95, 0.85, 0.65,
        0.45, 0.25, 0.1, 0.0, -0.05,
        -0.1, -0.1, -0.1, -0.1, -0.1
    ],

    "mega_bass": [
        1.0, 1.0, 1.0, 0.95, 0.8,
        0.6, 0.35, 0.15, 0.0, -0.1,
        -0.15, -0.2, -0.2, -0.2, -0.2
    ],

    "subwoofer": [
        1.0, 1.0, 1.0, 1.0, 0.9,
        0.75, 0.5, 0.25, 0.0, -0.15,
        -0.25, -0.3, -0.3, -0.3, -0.3
    ],

    "pop": [
        0.1, 0.15, 0.1, 0.05, 0.0,
        -0.05, -0.05, 0.0, 0.05, 0.1,
        0.1, 0.1, 0.05, 0.05, 0.0
    ],

    "rock": [
        0.3, 0.2, 0.1, 0.0, -0.1,
        -0.1, 0.0, 0.1, 0.2, 0.25,
        0.25, 0.25, 0.2, 0.2, 0.2
    ],

    "metal": [
        0.45, 0.35, 0.25, 0.15, 0.0,
        -0.05, 0.0, 0.15, 0.3, 0.4,
        0.4, 0.35, 0.25, 0.2, 0.2
    ],

    "edm": [
        0.9, 0.85, 0.8, 0.6, 0.45,
        0.3, 0.15, 0.1, 0.05, 0.0,
        -0.05, -0.05, -0.05, -0.05, -0.05
    ],

    "club": [
        0.75, 0.7, 0.65, 0.5, 0.35,
        0.2, 0.1, 0.05, 0.05, 0.1,
        0.1, 0.05, 0.0, 0.0, 0.0
    ],

    "dance": [
        0.7, 0.65, 0.55, 0.4, 0.25,
        0.15, 0.1, 0.05, 0.1, 0.15,
        0.2, 0.15, 0.1, 0.05, 0.0
    ],

    "klasyczna": [
        0.2, 0.15, 0.1, 0.05, 0.0,
        0.0, -0.05, -0.05, -0.05, 0.0,
        0.05, 0.1, 0.15, 0.2, 0.2
    ],

    "wokal": [
        -0.1, -0.1, -0.05, 0.0, 0.15,
        0.25, 0.3, 0.25, 0.2, 0.1,
        0.0, 0.0, -0.05, -0.1, -0.1
    ],

    "kino": [
        0.5, 0.45, 0.35, 0.25, 0.15,
        0.1, 0.05, 0.05, 0.1, 0.15,
        0.2, 0.2, 0.15, 0.1, 0.05
    ],

    "noc": [
        0.3, 0.25, 0.2, 0.15, 0.1,
        0.05, 0.0, 0.0, -0.05, -0.1,
        -0.1, -0.15, -0.15, -0.15, -0.15
    ]
}

class LavalinkUnavailableError(Exception):
    """Serwer Lavalink jest w tej chwili nieosiągalny (brak połączonego węzła)."""
    pass


def _is_node_unavailable_error(e: Exception) -> bool:
    if isinstance(e, wavelink.exceptions.InvalidNodeException):
        return True
    return "no nodes" in str(e).lower() or "connected state" in str(e).lower()


async def resolve_track(query: str) -> wavelink.Playable | None:
    """Zamienia zapytanie tekstowe albo URL (http/YouTube) na Playable."""
    search_query = query
    if query.startswith("http://") or query.startswith("https://"):
        search_query = normalize_audio_url(query)
    else:
        search_query = f"ytsearch:{query}"
    try:
        results = await wavelink.Playable.search(search_query)
    except Exception as e:
        if _is_node_unavailable_error(e):
            raise LavalinkUnavailableError(str(e)) from e
        print(f"[music] Błąd wyszukiwania Lavalink dla '{query}': {e}")
        return None
    if not results:
        return None
    if isinstance(results, wavelink.Playlist):
        return results.tracks[0] if results.tracks else None
    return results[0]


async def resolve_playlist_queries(url: str) -> list[str]:
    """Dla linku do playlisty (YouTube) zwraca listę URL-i pojedynczych utworów."""
    try:
        results = await wavelink.Playable.search(url)
    except Exception as e:
        if _is_node_unavailable_error(e):
            raise LavalinkUnavailableError(str(e)) from e
        raise
    if isinstance(results, wavelink.Playlist):
        return [t.uri for t in results.tracks if t.uri]
    if results:
        return [results[0].uri] if results[0].uri else []
    return []


MAX_CONSECUTIVE_FAILURES = 5


def _build_filters(eq_preset: str) -> wavelink.Filters:
    bands = EQ_PRESETS.get(eq_preset, EQ_PRESETS["flat"])
    filters = wavelink.Filters()
    filters.equalizer.set(bands=[{"band": i, "gain": g} for i, g in enumerate(bands)])
    return filters


class MusicPlayer(wavelink.Player):
    """Nasz Player - jeden obiekt na serwer, istnieje dopóki bot jest połączony z kanałem."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.text_channel = None
        self.query_queue: list[str] = []
        self.now_playing: wavelink.Playable | None = None

        # Radio - stała playlista grana w kółko w losowej kolejności
        self.radio_enabled = False
        self.radio_tracks: list[str] = []

        # Tymczasowa pauza
        self.paused_until: float = 0.0

        self.eq_preset: str = "flat"

        # Zabezpieczenie przed pętlą błędów (np. wiele zepsutych linków pod rząd)
        self._consecutive_failures = 0
        self._last_status_title: str | None = None

        # Zapowiedzi godzinowe ("Minęła właśnie ... w Bass FM")
        self._playing_announcement = False
        self._last_announced_key: tuple | None = None  # (data, godzina) ostatniej zapowiedzi
        self.default_eq_preset: str = "bas"

    # ---------- Kolejka ----------

    def add_to_queue(self, query: str):
        self.query_queue.append(query)

    def add_many_to_queue(self, queries: list[str]):
        self.query_queue.extend(queries)

    def clear_queue(self):
        self.query_queue.clear()

    async def start_if_idle(self):
        if self.paused_until and time.time() < self.paused_until:
            return
        if not self.playing and not self.paused:
            await self.play_next()

    async def play_next(self):
        if self._playing_announcement:
            self._playing_announcement = False
            try:
                await self.apply_eq_preset(self.default_eq_preset)
            except Exception as e:
                print(f"[music] Nie udało się przywrócić equalizera po zapowiedzi: {e}")

        if self.paused_until and time.time() < self.paused_until:
            return

        if not self.query_queue:
            if self.radio_enabled and self.radio_tracks:
                refill = list(self.radio_tracks)
                random.shuffle(refill)
                self.query_queue.extend(refill)
            else:
                self.now_playing = None
                if self.channel:
                    await clear_voice_channel_status(self.channel.id)
                return

        query = self.query_queue.pop(0)
        try:
            track = await resolve_track(query)
        except LavalinkUnavailableError:
            self.query_queue.insert(0, query)
            if self.text_channel:
                try:
                    await self.text_channel.send(
                        "⚠️ Serwer muzyczny (Lavalink) jest chwilowo niedostępny - "
                        "spróbuję wznowić automatycznie, gdy tylko wróci."
                    )
                except Exception:
                    pass
            return

        if track is None:
            self._consecutive_failures += 1
            if self._consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                msg = (
                    f"⚠️ {MAX_CONSECUTIVE_FAILURES} utworów pod rząd nie dało się odtworzyć "
                    "(sprawdź, czy linki w playliście są poprawne - bezpośrednie linki do "
                    "plików audio, nie linki do stron/podglądu). Wstrzymuję próby na chwilę, "
                    "spróbuję ponownie automatycznie."
                )
                print(f"[music] {msg}")
                if self.text_channel:
                    try:
                        await self.text_channel.send(msg)
                    except Exception:
                        pass
                self._consecutive_failures = 0
                return  # watchdog (co 30s w bot.py) spróbuje ponownie później
            await asyncio.sleep(0.5)  # nie bombarduj Lavalinka/API w kółko bez przerwy
            await self.play_next()
            return

        self._consecutive_failures = 0

        self.now_playing = track
        if self.channel and track.title != self._last_status_title:
            self._last_status_title = track.title
            await set_voice_channel_status(self.channel.id, f"🎵 {track.title}")
        await self.play(track)

    async def play_now(self, query: str) -> bool:
        """Odtwarza wybrany utwór NATYCHMIAST, z pominięciem kolejki. Po jego
        zakończeniu wraca do utworu, który grał wcześniej (jeśli był)."""
        try:
            track = await resolve_track(query)
        except LavalinkUnavailableError:
            raise
        if track is None:
            return False
        if self.now_playing is not None and self.now_playing.uri:
            self.query_queue.insert(0, self.now_playing.uri)
        self.now_playing = track
        if self.channel and track.title != self._last_status_title:
            self._last_status_title = track.title
            await set_voice_channel_status(self.channel.id, f"🎵 {track.title}")
        await self.play(track)
        return True

    async def play_announcement(self, url: str) -> bool:
        """Przerywa aktualny utwór i gra zapowiedź (np. "Minęła właśnie ... w Bass FM").
        Equalizer przełącza się na 'klasyczna' na czas zapowiedzi, a wraca do
        domyślnego presetu (self.default_eq_preset) automatycznie, gdy zapowiedź
        się skończy i ruszy kolejny normalny utwór (patrz play_next)."""
        try:
            await self.apply_eq_preset("klasyczna")
        except Exception as e:
            print(f"[music] Nie udało się ustawić equalizera na zapowiedź: {e}")
        try:
            ok = await self.play_now(url)
        except LavalinkUnavailableError:
            ok = False
        if ok:
            self._playing_announcement = True
        else:
            # nie udało się zagrać zapowiedzi - wracamy do normalnego equalizera od razu
            try:
                await self.apply_eq_preset(self.default_eq_preset)
            except Exception:
                pass
        return ok

    async def skip(self):
        await self.stop()  # wywoła zdarzenie końca utworu -> play_next() przez listener w bot.py

    # ---------- Tymczasowa pauza ----------

    async def pause_for(self, minutes: float):
        self.paused_until = time.time() + minutes * 60
        if self.playing:
            await self.pause(True)

    async def resume_now(self):
        self.paused_until = 0.0
        if self.paused:
            await self.pause(False)
        else:
            await self.start_if_idle()

    # ---------- Equalizer ----------

    async def apply_eq_preset(self, preset: str):
        preset = preset if preset in EQ_PRESETS else "flat"
        self.eq_preset = preset
        await self.set_filters(_build_filters(preset))

    # ---------- Radio (playlista w kółko) ----------

    def set_radio_tracks(self, tracks: list[str]):
        self.radio_tracks = list(tracks)
        self.radio_enabled = bool(tracks)

    def disable_radio(self):
        self.radio_enabled = False

    # ---------- Rozłączanie ----------

    async def leave(self):
        self.disable_radio()
        self.query_queue.clear()
        channel_id = self.channel.id if self.channel else None
        try:
            await self.disconnect()
        finally:
            if channel_id:
                await clear_voice_channel_status(channel_id)


class PlayerManager:
    """Pomocnik do znajdowania/tworzenia MusicPlayer na danym serwerze."""

    def __init__(self, bot):
        self.bot = bot

    def get(self, guild_id: int) -> MusicPlayer | None:
        guild = self.bot.get_guild(guild_id)
        if guild and isinstance(guild.voice_client, MusicPlayer):
            return guild.voice_client
        return None

    async def connect(self, channel) -> MusicPlayer:
        guild = channel.guild
        if isinstance(guild.voice_client, MusicPlayer):
            if guild.voice_client.channel and guild.voice_client.channel.id != channel.id:
                await guild.voice_client.move_to(channel)
            return guild.voice_client
        player: MusicPlayer = await channel.connect(cls=MusicPlayer, self_deaf=True)
        return player

    def all(self) -> list[MusicPlayer]:
        return [vc for vc in self.bot.voice_clients if isinstance(vc, MusicPlayer)]
