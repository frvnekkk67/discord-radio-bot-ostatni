"""
Konfiguracja bota-radia - wartości wrażliwe (tokeny, hasła) wczytywane są
ze zmiennych środowiskowych (plik .env lokalnie, Variables w Railway).
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Discord ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# --- Baza danych (playlista, ustawienia) ---
# Na Railway zalecane jest podpięcie Volume i ustawienie DB_PATH np. na
# /data/radio.db, żeby playlista/ustawienia przetrwały redeploy.
DB_PATH = os.getenv("DB_PATH", "radio.db")

# --- Lavalink (serwer muzyczny, osobna usługa - patrz folder lavalink/) ---
LAVALINK_HOST = os.getenv("LAVALINK_HOST", "")
LAVALINK_PORT = int(os.getenv("LAVALINK_PORT", "2333"))
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")
LAVALINK_SECURE = os.getenv("LAVALINK_SECURE", "false").lower() == "true"

# --- Dashboard (strona internetowa do sterowania radiem) ---
# Token wymagany do zalogowania się w dashboardzie - ustaw własny, losowy ciąg znaków.
DASHBOARD_TOKEN = os.getenv("DASHBOARD_TOKEN", "zmien-to-haslo")
# Port, na którym nasłuchuje dashboard (Railway ustawia PORT automatycznie).
PORT = int(os.getenv("PORT", "8080"))

# Domyślna głośność (0-150, gdzie 100 = normalna)
DEFAULT_VOLUME = int(os.getenv("DEFAULT_VOLUME", "70"))

# Strefa czasowa używana do zapowiedzi godzinowych ("Minęła właśnie ... w Bass FM")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Warsaw")
