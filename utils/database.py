"""
Warstwa bazy danych (aiosqlite) dla bota-radia:
 - ustawienia radia per serwer (kanał głosowy, rola admina, głośność, equalizer)
 - trwała playlista (lista utworów granych w kółko)
"""
import time
import aiosqlite

import config

_CREATE_SETTINGS = """
CREATE TABLE IF NOT EXISTS radio_settings (
    guild_id TEXT PRIMARY KEY,
    voice_channel_id TEXT,
    admin_role_id TEXT,
    volume INTEGER NOT NULL DEFAULT 70,
    eq_preset TEXT NOT NULL DEFAULT 'bas',
    paused_until REAL NOT NULL DEFAULT 0,
    radio_enabled INTEGER NOT NULL DEFAULT 0
);
"""

_CREATE_PLAYLIST = """
CREATE TABLE IF NOT EXISTS playlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL
);
"""

_CREATE_HOUR_ANNOUNCEMENTS = """
CREATE TABLE IF NOT EXISTS hour_announcements (
    guild_id TEXT NOT NULL,
    hour INTEGER NOT NULL,
    url TEXT NOT NULL,
    PRIMARY KEY (guild_id, hour)
);
"""


class Database:
    def __init__(self, path: str = None):
        self.path = path or config.DB_PATH
        self._conn: aiosqlite.Connection | None = None

    async def connect(self):
        self._conn = await aiosqlite.connect(self.path)
        await self._conn.execute(_CREATE_SETTINGS)
        await self._conn.execute(_CREATE_PLAYLIST)
        await self._conn.execute(_CREATE_HOUR_ANNOUNCEMENTS)
        await self._conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()

    # ---------- Ustawienia radia ----------

    async def get_settings(self, guild_id: int) -> dict:
        cur = await self._conn.execute(
            "SELECT voice_channel_id, admin_role_id, volume, eq_preset, paused_until, radio_enabled "
            "FROM radio_settings WHERE guild_id = ?",
            (str(guild_id),),
        )
        row = await cur.fetchone()
        await cur.close()
        if row is None:
            return {
                "voice_channel_id": None, "admin_role_id": None,
                "volume": config.DEFAULT_VOLUME, "eq_preset": "flat",
                "paused_until": 0.0, "radio_enabled": False,
            }
        return {
            "voice_channel_id": int(row[0]) if row[0] else None,
            "admin_role_id": int(row[1]) if row[1] else None,
            "volume": row[2], "eq_preset": row[3],
            "paused_until": row[4], "radio_enabled": bool(row[5]),
        }

    async def _upsert(self, guild_id: int, **fields):
        await self._conn.execute(
            "INSERT INTO radio_settings (guild_id) VALUES (?) ON CONFLICT(guild_id) DO NOTHING",
            (str(guild_id),),
        )
        if fields:
            set_clause = ", ".join(f"{k} = ?" for k in fields)
            await self._conn.execute(
                f"UPDATE radio_settings SET {set_clause} WHERE guild_id = ?",
                (*fields.values(), str(guild_id)),
            )
        await self._conn.commit()

    async def set_voice_channel(self, guild_id: int, channel_id: int, enabled: bool = True):
        await self._upsert(guild_id, voice_channel_id=str(channel_id), radio_enabled=int(enabled))

    async def set_radio_enabled(self, guild_id: int, enabled: bool):
        await self._upsert(guild_id, radio_enabled=int(enabled))

    async def set_admin_role(self, guild_id: int, role_id: int):
        await self._upsert(guild_id, admin_role_id=str(role_id))

    async def set_volume(self, guild_id: int, volume: int):
        await self._upsert(guild_id, volume=max(0, min(150, volume)))

    async def set_eq_preset(self, guild_id: int, preset: str):
        await self._upsert(guild_id, eq_preset=preset)

    async def set_paused_until(self, guild_id: int, timestamp: float):
        await self._upsert(guild_id, paused_until=timestamp)

    async def get_all_radio_guilds(self) -> list[dict]:
        cur = await self._conn.execute(
            "SELECT guild_id, voice_channel_id, volume, eq_preset FROM radio_settings WHERE radio_enabled = 1"
        )
        rows = await cur.fetchall()
        await cur.close()
        return [
            {"guild_id": int(g), "voice_channel_id": int(vc), "volume": vol, "eq_preset": eq}
            for g, vc, vol, eq in rows if vc
        ]

    # ---------- Playlista ----------

    async def get_playlist(self, guild_id: int) -> list[dict]:
        cur = await self._conn.execute(
            "SELECT id, url, title FROM playlist WHERE guild_id = ? ORDER BY position ASC",
            (str(guild_id),),
        )
        rows = await cur.fetchall()
        await cur.close()
        return [{"id": r[0], "url": r[1], "title": r[2]} for r in rows]

    async def add_track(self, guild_id: int, url: str, title: str) -> int:
        cur = await self._conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM playlist WHERE guild_id = ?",
            (str(guild_id),),
        )
        (next_pos,) = await cur.fetchone()
        await cur.close()
        cur = await self._conn.execute(
            "INSERT INTO playlist (guild_id, position, url, title) VALUES (?, ?, ?, ?)",
            (str(guild_id), next_pos, url, title),
        )
        await self._conn.commit()
        return cur.lastrowid

    async def add_tracks(self, guild_id: int, tracks: list[tuple[str, str]]):
        cur = await self._conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM playlist WHERE guild_id = ?",
            (str(guild_id),),
        )
        (next_pos,) = await cur.fetchone()
        await cur.close()
        rows = [(str(guild_id), next_pos + i, url, title) for i, (url, title) in enumerate(tracks)]
        await self._conn.executemany(
            "INSERT INTO playlist (guild_id, position, url, title) VALUES (?, ?, ?, ?)", rows
        )
        await self._conn.commit()

    async def remove_track(self, guild_id: int, track_id: int):
        await self._conn.execute(
            "DELETE FROM playlist WHERE guild_id = ? AND id = ?", (str(guild_id), track_id)
        )
        await self._conn.commit()

    async def clear_playlist(self, guild_id: int):
        await self._conn.execute("DELETE FROM playlist WHERE guild_id = ?", (str(guild_id),))
        await self._conn.commit()

    # ---------- Zapowiedzi godzinowe ----------

    async def set_hour_announcement(self, guild_id: int, hour: int, url: str):
        await self._conn.execute(
            "INSERT INTO hour_announcements (guild_id, hour, url) VALUES (?, ?, ?) "
            "ON CONFLICT(guild_id, hour) DO UPDATE SET url = excluded.url",
            (str(guild_id), hour, url),
        )
        await self._conn.commit()

    async def remove_hour_announcement(self, guild_id: int, hour: int):
        await self._conn.execute(
            "DELETE FROM hour_announcements WHERE guild_id = ? AND hour = ?",
            (str(guild_id), hour),
        )
        await self._conn.commit()

    async def get_hour_announcements(self, guild_id: int) -> dict[int, str]:
        cur = await self._conn.execute(
            "SELECT hour, url FROM hour_announcements WHERE guild_id = ? ORDER BY hour ASC",
            (str(guild_id),),
        )
        rows = await cur.fetchall()
        await cur.close()
        return {hour: url for hour, url in rows}
