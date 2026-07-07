"""
Komendy administracyjne:
 - /rolaadmina     - ustawia rolę uprawnioną do zarządzania radiem
 - /polacz         - łączy bota z kanałem głosowym i włącza radio (playlistę w kółko)
 - /playlistadodaj - dodaje utwór do stałej playlisty radiowej
 - /playlistausun  - usuwa utwór z playlisty (po ID z /playlistalista)
 - /playlistalista - pokazuje playlistę radiową
"""
import discord
from discord import app_commands
from discord.ext import commands

from utils.player import resolve_playlist_queries, LavalinkUnavailableError
from utils.permissions import bot_admin_only, NotBotAdmin


class Settings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="rolaadmina", description="Ustawia rolę, która może zarządzać radiem bota")
    @app_commands.describe(rola="Rola, która od teraz będzie mogła zarządzać botem")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def rolaadmina(self, interaction: discord.Interaction, rola: discord.Role):
        await self.bot.db.set_admin_role(interaction.guild_id, rola.id)
        await interaction.response.send_message(
            f"Od teraz rola {rola.mention} może zarządzać botem (oprócz administratorów, którzy mają dostęp zawsze). ✅"
        )

    @app_commands.command(name="polacz", description="Łączy bota z kanałem i włącza radio (playlistę w kółko)")
    @app_commands.describe(kanal="Kanał głosowy, na którym bot ma siedzieć i grać radio")
    @bot_admin_only()
    async def polacz(self, interaction: discord.Interaction, kanal: discord.VoiceChannel):
        await interaction.response.defer()
        try:
            player = await self.bot.players.connect(kanal)
        except Exception as e:
            await interaction.followup.send(f"Nie mogę połączyć się z serwerem muzycznym (Lavalink). Błąd: {e}")
            return
        player.text_channel = interaction.channel

        playlist = await self.bot.db.get_playlist(interaction.guild_id)
        if not playlist:
            await interaction.followup.send(
                "⚠️ Playlista radiowa jest pusta - dodaj utwory przez `/playlistadodaj` "
                "albo w dashboardzie, a potem użyj `/polacz` ponownie."
            )
            return

        settings = await self.bot.db.get_settings(interaction.guild_id)
        player.set_radio_tracks([t["url"] for t in playlist])
        await player.apply_eq_preset(settings["eq_preset"])
        await player.set_volume(settings["volume"])
        await self.bot.db.set_voice_channel(interaction.guild_id, kanal.id, enabled=True)

        try:
            await player.start_if_idle()
        except LavalinkUnavailableError:
            pass

        await interaction.followup.send(
            f"📻 Radio włączone na **{kanal.name}** - gram playlistę ({len(playlist)} utworów) w kółko."
        )

    @app_commands.command(name="playlistadodaj", description="Dodaje utwór do stałej playlisty radiowej")
    @app_commands.describe(link="Link YouTube albo bezpośredni link do pliku audio", tytul="Nazwa utworu (opcjonalnie)")
    @bot_admin_only()
    async def playlistadodaj(self, interaction: discord.Interaction, link: str, tytul: str = None):
        await interaction.response.defer()
        title = tytul or link
        await self.bot.db.add_track(interaction.guild_id, link, title)
        player = self.bot.players.get(interaction.guild_id)
        if player and player.radio_enabled:
            player.radio_tracks.append(link)
        await interaction.followup.send(f"Dodano do playlisty radiowej: **{title}** ✅")

    @app_commands.command(name="playlistadodajplayliste", description="Dodaje wszystkie utwory z linku do playlisty YouTube")
    @app_commands.describe(link="Link do playlisty YouTube")
    @bot_admin_only()
    async def playlistadodajplayliste(self, interaction: discord.Interaction, link: str):
        await interaction.response.defer()
        try:
            urls = await resolve_playlist_queries(link)
        except LavalinkUnavailableError:
            await interaction.followup.send("⚠️ Serwer muzyczny (Lavalink) jest chwilowo niedostępny.")
            return
        if not urls:
            await interaction.followup.send("Nie znalazłem żadnych utworów pod tym linkiem.")
            return
        await self.bot.db.add_tracks(interaction.guild_id, [(u, u) for u in urls])
        player = self.bot.players.get(interaction.guild_id)
        if player and player.radio_enabled:
            player.radio_tracks.extend(urls)
        await interaction.followup.send(f"Dodano **{len(urls)}** utworów do playlisty radiowej. ✅")

    @app_commands.command(name="playlistausun", description="Usuwa utwór z playlisty radiowej (po ID z /playlistalista)")
    @app_commands.describe(id="ID utworu do usunięcia")
    @bot_admin_only()
    async def playlistausun(self, interaction: discord.Interaction, id: int):
        await self.bot.db.remove_track(interaction.guild_id, id)
        playlist = await self.bot.db.get_playlist(interaction.guild_id)
        player = self.bot.players.get(interaction.guild_id)
        if player:
            player.set_radio_tracks([t["url"] for t in playlist])
        await interaction.response.send_message(f"Usunięto utwór #{id} z playlisty. 🗑️")

    @app_commands.command(name="playlistalista", description="Pokazuje playlistę radiową")
    async def playlistalista(self, interaction: discord.Interaction):
        playlist = await self.bot.db.get_playlist(interaction.guild_id)
        if not playlist:
            await interaction.response.send_message("Playlista radiowa jest pusta.")
            return
        lines = [f"**Playlista radiowa ({len(playlist)}):**"]
        for t in playlist[:25]:
            lines.append(f"`#{t['id']}` {t['title']}")
        if len(playlist) > 25:
            lines.append(f"...i {len(playlist) - 25} więcej (pełna lista w dashboardzie)")
        await interaction.response.send_message("\n".join(lines))

    async def _permission_error(self, interaction: discord.Interaction, error):
        if isinstance(error, (app_commands.MissingPermissions, NotBotAdmin)):
            await interaction.response.send_message(
                "Nie masz uprawnień do tej komendy. Potrzebujesz roli administracyjnej bota "
                "(ustawionej przez `/rolaadmina`) albo uprawnienia **Zarządzaj serwerem**.",
                ephemeral=True,
            )
        else:
            raise error

    @rolaadmina.error
    async def rolaadmina_error(self, interaction, error):
        await self._permission_error(interaction, error)

    @polacz.error
    async def polacz_error(self, interaction, error):
        await self._permission_error(interaction, error)

    @playlistadodaj.error
    async def playlistadodaj_error(self, interaction, error):
        await self._permission_error(interaction, error)

    @playlistadodajplayliste.error
    async def playlistadodajplayliste_error(self, interaction, error):
        await self._permission_error(interaction, error)

    @playlistausun.error
    async def playlistausun_error(self, interaction, error):
        await self._permission_error(interaction, error)


async def setup(bot: commands.Bot):
    await bot.add_cog(Settings(bot))
