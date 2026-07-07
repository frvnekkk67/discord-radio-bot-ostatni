# Skąd wziąć pliki audio dla radia

Radio gra listę utworów w kółko (losowa kolejność). Każdy utwór to albo:
- bezpośredni link do pliku audio (mp3, ogg, m4a...), albo
- link do YouTube (jeśli wolisz nie hostować własnych plików).

## Hostowanie własnych plików na GitHub (najprościej, za darmo)

**Opcja A - GitHub Releases (zalecane dla większych/plikowych bibliotek):**
1. W swoim repozytorium wejdź w **Releases** → **Draft a new release**.
2. Nie musisz podpinać go pod żaden tag/branch - możesz stworzyć release
   tylko po to, żeby wgrać do niego pliki (**Attach binaries**).
3. Wgraj tam swoje pliki mp3.
4. Kliknij prawym na plik po opublikowaniu releasu → "Copy link address" -
   to jest bezpośredni URL, który wklejasz w dashboardzie/komendzie
   `/playlistadodaj`. GitHub Releases nie ma większych limitów rozmiaru
   pojedynczego pliku (do 2 GB) i serwuje pliki z CDN.

**Opcja B - zwykłe pliki w repo (dla małych/kilku plików):**
1. Wrzuć pliki mp3 do folderu w repo (np. `radio/files/`).
2. Użyj linku w formacie:
   `https://raw.githubusercontent.com/TWOJ_LOGIN/TWOJE_REPO/main/radio/files/nazwa.mp3`
3. Uwaga: GitHub ogranicza pojedynczy plik w zwykłym repo do 100 MB, a duże
   ilości dużych plików binarnych w historii gita nie są zalecane - do
   większej biblioteki lepsza jest Opcja A albo zewnętrzny hosting plików.

## Dodawanie utworów do playlisty radiowej

Najwygodniej przez **dashboard** (sekcja "Playlista radiowa" - wklej link,
opcjonalnie tytuł, "Dodaj"), albo komendą na Discordzie:

```
/playlistadodaj link:https://... tytul:Nazwa utworu
```

Plik `playlist.example.json` w tym folderze to tylko przykład formatu -
bot go nie wczytuje automatycznie, to informacja poglądowa. Właściwa
playlista jest przechowywana w bazie danych bota (żeby dało się nią
zarządzać z dashboardu bez redeployu).
