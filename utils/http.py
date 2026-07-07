"""
Jedna, długo żyjąca sesja aiohttp dla całego bota, zamiast tworzenia nowej
sesji (i nowego połączenia TCP) dla każdego pojedynczego zapytania.

Tworzenie mnóstwa krótko żyjących `aiohttp.ClientSession()` (np. po jednej na
każde zapytanie do Discord API o status kanału głosowego) potrafi przy
większym ruchu wywołać burzę błędów w event loopie ("Exception in callback
_SelectorSocketTransport._read_ready()"), która zapycha logi i przeciąża
hosting. Współdzielenie jednej sesji (ze swoim connection poolem, keep-alive)
jest też zwyczajnie zalecaną praktyką aiohttp.
"""
import aiohttp

_session: aiohttp.ClientSession | None = None


async def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session


async def close_session():
    global _session
    if _session is not None and not _session.closed:
        await _session.close()
    _session = None
