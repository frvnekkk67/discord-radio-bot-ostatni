"""
Ustawianie "statusu kanału głosowego" (funkcja Discorda widoczna pod nazwą
kanału głosowego) na tytuł aktualnie granego utworu.
"""
import config
from utils.http import get_session

API_BASE = "https://discord.com/api/v10"


async def set_voice_channel_status(channel_id: int, status: str):
    status = (status or "")[:500]
    headers = {
        "Authorization": f"Bot {config.DISCORD_TOKEN}",
        "Content-Type": "application/json",
    }
    url = f"{API_BASE}/channels/{channel_id}/voice-status"
    try:
        session = await get_session()
        async with session.put(url, headers=headers, json={"status": status}) as resp:
            if resp.status == 429:
                return  # rate limit Discorda - nieszkodliwe, po prostu pomijamy tę aktualizację
            if resp.status not in (200, 204):
                text = await resp.text()
                print(f"[voice_status] Nie udało się ustawić statusu kanału ({resp.status}): {text}")
    except Exception as e:
        print(f"[voice_status] Błąd ustawiania statusu kanału: {e}")


async def clear_voice_channel_status(channel_id: int):
    await set_voice_channel_status(channel_id, "")
