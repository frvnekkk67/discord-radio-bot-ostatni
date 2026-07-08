# Discord Radio Bot + Dashboard

Bot Discord, który działa jak radio: siedzi 24/7 na wybranym kanale
głosowym i gra Twoją playlistę w kółko (pliki audio, które sam hostujesz,
albo linki YouTube). Sterowanie odbywa się głównie przez **dashboard
webowy** (skip, "zagraj teraz" z pominięciem kolejki, tymczasowa pauza,
equalizer, zarządzanie playlistą), a najważniejsze komendy są też dostępne
na Discordzie.

Brak jakiegokolwiek śledzenia aktywności/rankingu - to czyste radio.

## Architektura: bot + Lavalink + dashboard (dwie usługi na Railway)

Odtwarzanie muzyki idzie przez **Lavalink** - osobny serwer, standard
branżowy dla botów muzycznych, dużo bardziej odporny na blokady YouTube niż
odtwarzanie bezpośrednio z kodu bota. Dashboard webowy działa **w tym samym
procesie co bot** (ten sam serwis Railway) - nie trzeba niczego dodatkowo
wdrażać dla panelu.

To oznacza dwie usługi w jednym projekcie Railway:
1. **bot** (ten kod Pythona, z dashboardem w środku)
2. **lavalink** (folder `lavalink/`)

## Komendy na Discordzie

| Komenda | Opis |
|---|---|
| `/graj <zapytanie>` | Dogrywa utwór do kolejki (nazwa, link YouTube, bezpośredni link do pliku audio) |
| `/nastepny <zapytanie>` | Odtwarza wybrany utwór NATYCHMIAST, z pominięciem kolejki - po nim wraca do tego, co grało wcześniej |
| `/pomin` | Pomija aktualny utwór |
| `/stop [minuty]` | Zatrzymuje granie na chwilę (domyślnie 1 min) - wznawia się samo |
| `/wznow` | Wznawia granie / anuluje tymczasową pauzę |
| `/glosnosc <0-150>` | Ustawia głośność |
| `/eq <preset>` | Equalizer: flat / bas / pop / rock / klasyczna / wokal |
| `/kolejka` | Pokazuje aktualną kolejkę |
| `/rozlacz` | *(Zarządzaj serwerem)* Rozłącza bota i wyłącza radio |
| `/rolaadmina <rola>` | *(Zarządzaj serwerem)* Ustawia rolę uprawnioną do zarządzania radiem |
| `/polacz <kanal>` | *(rola admina bota)* Łączy bota z kanałem i włącza radio |
| `/playlistadodaj <link> [tytul]` | *(rola admina bota)* Dodaje utwór do stałej playlisty radiowej |
| `/playlistadodajplayliste <link>` | *(rola admina bota)* Dogrywa całą playlistę YouTube do playlisty radiowej |
| `/playlistausun <id>` | *(rola admina bota)* Usuwa utwór z playlisty |
| `/playlistalista` | Pokazuje playlistę radiową |
| `/zapowiedz <godzina> <link>` | *(rola admina bota)* Ustawia zapowiedź (mp3) odtwarzaną o pełnej godzinie |
| `/usunzapowiedz <godzina>` | *(rola admina bota)* Usuwa zapowiedź dla danej godziny |
| `/listazapowiedzi` | Pokazuje skonfigurowane zapowiedzi godzinowe |

### Zapowiedzi godzinowe ("Minęła właśnie jedenasta w Bass FM")

Radio może automatycznie przerywać aktualny utwór o pełnej godzinie i grać
Twój własny jingiel (mp3, który sam nagrasz/zrobisz), np. "Minęła właśnie
jedenasta w Bass FM". Działa tak:
- Ustawiasz zapowiedź dla wybranych godzin (0-23) - przez `/zapowiedz` albo
  w dashboardzie (sekcja "Zapowiedzi godzinowe").
- Bot sam sprawdza aktualny czas (strefa czasowa z `TIMEZONE`, domyślnie
  `Europe/Warsaw`) i o pełnej godzinie, dla której masz ustawioną zapowiedź,
  przerywa aktualny utwór, gra zapowiedź, po czym wraca do muzyki.
- Equalizer na czas zapowiedzi przełącza się na "klasyczna" (żeby głos był
  czytelny), a zaraz po niej wraca do Twojego normalnego ustawienia
  (domyślnie "bas").
- Godziny bez ustawionej zapowiedzi po prostu nic nie robią - grają dalej normalnie.

Więcej (equalizer, zarządzanie playlistą, podgląd na żywo) jest wygodniej
dostępne na dashboardzie - patrz niżej.

## Dashboard webowy

Po wdrożeniu (sekcja 4 niżej) dashboard jest dostępny pod publicznym adresem
Twojej usługi bota na Railway. Loguje się tokenem (`DASHBOARD_TOKEN` ze
zmiennych środowiskowych). Z panelu można:
- widzieć co gra teraz i podgląd kolejki (odświeża się automatycznie),
- połączyć/rozłączyć bota z wybranym kanałem głosowym,
- pominąć utwór, zagrać coś natychmiast (z pominięciem kolejki),
- zatrzymać granie na X minut (z automatycznym wznowieniem),
- zmieniać głośność suwakiem i equalizer z listy presetów,
- dodawać/usuwać utwory ze stałej playlisty radiowej.

---

## 1. Zakładanie bota na Discordzie

1. Wejdź na https://discord.com/developers/applications → **New Application**.
2. Zakładka **Bot** → **Reset Token** → skopiuj token (to Twój `DISCORD_TOKEN`).
3. Tam samo włącz **Privileged Gateway Intents**:
   - `SERVER MEMBERS INTENT`
   - `MESSAGE CONTENT INTENT`
4. Zakładka **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`, `Read Message History`, `Connect`,
     `Speak`, `View Channels`, `Manage Channels` (do statusu kanału głosowego
     z tytułem utworu)
   - Skopiuj wygenerowany link i otwórz go, żeby zaprosić bota na swój serwer.

## 2. Skąd wziąć muzykę do playlisty

Zobacz `radio/README.md` - krótka instrukcja jak za darmo hostować własne
pliki mp3 na GitHubie (Releases albo raw pliki w repo), plus możliwość
zwykłych linków YouTube. Playlistę zarządza się potem z dashboardu albo
komendami `/playlistadodaj` / `/playlistadodajplayliste`.

## 3. Uruchomienie lokalnie

Potrzebujesz lokalnie działającego Lavalinka (Java 17+):

```bash
# Pobierz Lavalink.jar z https://github.com/lavalink-devs/Lavalink/releases
# Umieść je w folderze lavalink/ obok application.yml, potem:
cd lavalink
java -jar Lavalink.jar
```

W drugim terminalu uruchom bota:

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Skopiuj `.env.example` do `.env`, uzupełnij `DISCORD_TOKEN` i `DASHBOARD_TOKEN`
(domyślne `LAVALINK_HOST=localhost` / `LAVALINK_PORT=2333` pasują do
lokalnego Lavalinka), następnie:

```bash
python bot.py
```

Dashboard będzie dostępny pod http://localhost:8080

## 4. Wdrożenie bota na Railway przez GitHub

1. Wrzuć ten cały folder jako repozytorium na GitHub:
   ```bash
   git init
   git add .
   git commit -m "Discord radio bot + dashboard"
   git branch -M main
   git remote add origin https://github.com/TWOJ_LOGIN/TWOJE_REPO.git
   git push -u origin main
   ```
   (`.gitignore` dba o to, żeby `.env` i baza danych NIE trafiły do repo)

2. Wejdź na https://railway.app → **New Project** → **Deploy from GitHub repo**
   → wybierz swoje repozytorium (Root Directory zostaw domyślne).

3. W **Variables** tej usługi dodaj:
   - `DISCORD_TOKEN`
   - `DASHBOARD_TOKEN` - wymyśl własny, losowy ciąg znaków
   - `DB_PATH` = `/data/radio.db` *(patrz punkt niżej o Volume)*
   - `LAVALINK_HOST`, `LAVALINK_PORT`, `LAVALINK_PASSWORD` - uzupełnisz je
     po wdrożeniu usługi Lavalink (sekcja 5)

4. **Trwałość playlisty (Volume):** żeby playlista/ustawienia nie znikały
   przy redeployu:
   - Usługa bota → zakładka **Volumes** → **New Volume** → Mount path `/data`

5. Zakładka **Settings** → **Networking** → **Generate Domain**, żeby dostać
   publiczny adres dashboardu (Railway sam podpina zmienną `PORT`).

> **Uwaga:** Railway obecnie buduje projekty swoim builderem **Railpack**
> (wykrywa Pythona i wersję automatycznie na podstawie `requirements.txt`).
> Nie trzeba (i nie warto) wymuszać konkretnej wersji Pythona plikiem
> `.python-version` - część starszych wersji nie ma zweryfikowanych
> "GitHub attestations", co powoduje błąd builda (`mise ERROR ... No GitHub
> artifact attestations found`). Jeśli mimo wszystko chcesz przypiąć
> konkretną wersję i trafisz na ten błąd, dodaj zmienną środowiskową
> `MISE_PYTHON_GITHUB_ATTESTATIONS=false` w usłudze bota.

## 5. Wdrożenie serwera Lavalink na Railway

1. W TYM SAMYM projekcie: **New** → **GitHub Repo** → to samo repozytorium
   jeszcze raz (druga usługa).
2. **Settings** → **Root Directory** → ustaw na `lavalink`.
3. W **Variables** tej usługi dodaj `LAVALINK_SERVER_PASSWORD` (dowolne hasło).
4. Zdeployuj, poczekaj aż wystartuje.
5. Wróć do usługi **bota** i uzupełnij zmienne z punktu 3 (sekcja 4):
   - `LAVALINK_HOST` = prywatna domena usługi Lavalink (Settings → Networking
     → Private Networking), np. `lavalink.railway.internal`
   - `LAVALINK_PORT` = `2333`
   - `LAVALINK_PASSWORD` = to samo hasło co w kroku 3

### Rozwiązywanie problemów z Lavalink/YouTube

- Jeśli wyszukiwanie/odtwarzanie YouTube przestanie działać, sprawdź
  https://github.com/lavalink-devs/youtube-source po najnowszą wersję
  pluginu (podmień wersję w `lavalink/application.yml`).
- **Błąd "Something went wrong while looking up the track" / `severity=fault`:**
  sprawdź logi usługi **Lavalink** (nie bota) w momencie próby - tam jest
  prawdziwa przyczyna. Najczęściej pomaga aktualizacja pluginu albo dodanie
  PoTokenu (sekcja `pot:` w `application.yml`).
- Pliki hostowane bezpośrednio (mp3 z GitHub Releases itp.) nie mają tego
  problemu - to obejście specyficzne dla YouTube, więc jeśli chcesz
  maksymalnej niezawodności, stawiaj głównie na własne pliki audio.

## Znane ograniczenia

- Playlista i ustawienia trzymane są w SQLite - bez podpiętego Volume na
  Railway znikną przy każdym redeployu.
- Dashboard używa prostego tokenu jako hasła - nie udostępniaj go publicznie
  bez potrzeby, to pełna kontrola nad botem.
- Od 2026 Discord wymaga szyfrowania end-to-end (DAVE) dla połączeń
  głosowych - `requirements.txt` zawiera `dave.py`, które to obsługuje.
- Status kanału głosowego (tytuł granego utworu pod nazwą kanału) wymaga
  uprawnienia bota "Zarządzaj kanałami" na tym kanale.
