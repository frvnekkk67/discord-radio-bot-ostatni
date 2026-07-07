"""
Backend dashboardu webowego - REST API do sterowania radiem, osadzone w tym
samym procesie co bot Discord (współdzieli event loop, więc może wywoływać
metody MusicPlayer bezpośrednio, bez żadnej dodatkowej komunikacji między
procesami).

Autoryzacja: prosty token (nagłówek "Authorization: Bearer <token>"),
porównywany ze zmienną środowiskową DASHBOARD_TOKEN.
"""
import os

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
from utils.player import EQ_PRESETS, LavalinkUnavailableError

app = FastAPI(title="Radio Bot Dashboard")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


def get_bot():
    return app.state.bot


def check_token(authorization: str | None = Header(None)):
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not token or token != config.DASHBOARD_TOKEN:
        raise HTTPException(status_code=401, detail="Nieprawidłowy token dostępu")
    return True


class GuildIdBody(BaseModel):
    guild_id: int


class ConnectBody(BaseModel):
    guild_id: int
    channel_id: int


class PlayNowBody(BaseModel):
    guild_id: int
    query: str


class VolumeBody(BaseModel):
    guild_id: int
    value: int


class EqBody(BaseModel):
    guild_id: int
    preset: str


class PauseBody(BaseModel):
    guild_id: int
    minutes: float = 1.0


class PlaylistAddBody(BaseModel):
    guild_id: int
    url: str
    title: str | None = None


# ---------- Serwery / kanały ----------

@app.get("/api/guilds")
async def list_guilds(auth=Depends(check_token)):
    bot = get_bot()
    return [{"id": str(g.id), "name": g.name} for g in bot.guilds]


@app.get("/api/voice_channels")
async def list_voice_channels(guild_id: int, auth=Depends(check_token)):
    bot = get_bot()
    guild = bot.get_guild(guild_id)
    if not guild:
        raise HTTPException(404, "Serwer nie znaleziony")
    return [{"id": str(c.id), "name": c.name} for c in guild.voice_channels]


# ---------- Status ----------

@app.get("/api/status")
async def status(guild_id: int, auth=Depends(check_token)):
    bot = get_bot()
    settings = await bot.db.get_settings(guild_id)
    player = bot.players.get(guild_id)
    if not player:
        return {
            "connected": False, "channel": None, "now_playing": None,
            "paused": False, "paused_until": settings["paused_until"],
            "volume": settings["volume"], "eq_preset": settings["eq_preset"],
            "radio_enabled": settings["radio_enabled"], "queue": [],
        }
    return {
        "connected": True,
        "channel": player.channel.name if player.channel else None,
        "now_playing": player.now_playing.title if player.now_playing else None,
        "paused": player.paused,
        "paused_until": player.paused_until,
        "volume": player.volume,
        "eq_preset": player.eq_preset,
        "radio_enabled": player.radio_enabled,
        "queue": player.query_queue[:20],
    }


# ---------- Połączenie ----------

@app.post("/api/connect")
async def connect(body: ConnectBody, auth=Depends(check_token)):
    bot = get_bot()
    guild = bot.get_guild(body.guild_id)
    if not guild:
        raise HTTPException(404, "Serwer nie znaleziony")
    channel = guild.get_channel(body.channel_id)
    if not channel:
        raise HTTPException(404, "Kanał nie znaleziony")

    player = await bot.players.connect(channel)
    player.text_channel = None

    playlist = await bot.db.get_playlist(body.guild_id)
    player.set_radio_tracks([t["url"] for t in playlist])

    settings = await bot.db.get_settings(body.guild_id)
    await player.apply_eq_preset(settings["eq_preset"])
    await player.set_volume(settings["volume"])
    await bot.db.set_voice_channel(body.guild_id, body.channel_id, enabled=True)

    try:
        await player.start_if_idle()
    except LavalinkUnavailableError:
        raise HTTPException(503, "Lavalink jest chwilowo niedostępny")

    return {"ok": True}


@app.post("/api/disconnect")
async def disconnect(body: GuildIdBody, auth=Depends(check_token)):
    bot = get_bot()
    await bot.db.set_radio_enabled(body.guild_id, False)
    player = bot.players.get(body.guild_id)
    if player:
        await player.leave()
    return {"ok": True}


# ---------- Sterowanie odtwarzaniem ----------

@app.post("/api/skip")
async def skip(body: GuildIdBody, auth=Depends(check_token)):
    bot = get_bot()
    player = bot.players.get(body.guild_id)
    if not player:
        raise HTTPException(400, "Bot nie jest połączony")
    await player.skip()
    return {"ok": True}


@app.post("/api/play_now")
async def play_now(body: PlayNowBody, auth=Depends(check_token)):
    bot = get_bot()
    player = bot.players.get(body.guild_id)
    if not player:
        raise HTTPException(400, "Bot nie jest połączony z żadnym kanałem")
    try:
        ok = await player.play_now(body.query)
    except LavalinkUnavailableError:
        raise HTTPException(503, "Lavalink jest chwilowo niedostępny")
    if not ok:
        raise HTTPException(404, "Nie znaleziono utworu")
    return {"ok": True}


@app.post("/api/pause_temp")
async def pause_temp(body: PauseBody, auth=Depends(check_token)):
    bot = get_bot()
    player = bot.players.get(body.guild_id)
    if not player:
        raise HTTPException(400, "Bot nie jest połączony")
    minutes = max(0.1, min(180, body.minutes))
    await player.pause_for(minutes)
    await bot.db.set_paused_until(body.guild_id, player.paused_until)
    return {"ok": True, "paused_until": player.paused_until}


@app.post("/api/resume")
async def resume(body: GuildIdBody, auth=Depends(check_token)):
    bot = get_bot()
    player = bot.players.get(body.guild_id)
    if not player:
        raise HTTPException(400, "Bot nie jest połączony")
    await player.resume_now()
    await bot.db.set_paused_until(body.guild_id, 0)
    return {"ok": True}


@app.post("/api/volume")
async def set_volume(body: VolumeBody, auth=Depends(check_token)):
    bot = get_bot()
    value = max(0, min(150, body.value))
    player = bot.players.get(body.guild_id)
    if player:
        await player.set_volume(value)
    await bot.db.set_volume(body.guild_id, value)
    return {"ok": True}


@app.get("/api/eq_presets")
async def eq_presets(auth=Depends(check_token)):
    return {"presets": list(EQ_PRESETS.keys())}


@app.post("/api/eq")
async def set_eq(body: EqBody, auth=Depends(check_token)):
    bot = get_bot()
    player = bot.players.get(body.guild_id)
    if player:
        await player.apply_eq_preset(body.preset)
    await bot.db.set_eq_preset(body.guild_id, body.preset)
    return {"ok": True}


# ---------- Playlista ----------

@app.get("/api/playlist")
async def get_playlist(guild_id: int, auth=Depends(check_token)):
    bot = get_bot()
    return await bot.db.get_playlist(guild_id)


@app.post("/api/playlist/add")
async def add_track(body: PlaylistAddBody, auth=Depends(check_token)):
    bot = get_bot()
    title = body.title or body.url
    track_id = await bot.db.add_track(body.guild_id, body.url, title)
    player = bot.players.get(body.guild_id)
    if player and player.radio_enabled:
        player.radio_tracks.append(body.url)
    return {"ok": True, "id": track_id}


@app.delete("/api/playlist/{track_id}")
async def remove_track(track_id: int, guild_id: int, auth=Depends(check_token)):
    bot = get_bot()
    await bot.db.remove_track(guild_id, track_id)
    playlist = await bot.db.get_playlist(guild_id)
    player = bot.players.get(guild_id)
    if player:
        player.set_radio_tracks([t["url"] for t in playlist])
    return {"ok": True}


# ---------- Statyczny frontend ----------

_static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
