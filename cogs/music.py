"""
Komendy muzyczne bota-radia. Większość zaawansowanych funkcji (equalizer,
zarządzanie playlistą, statystyki) jest dostępna na dashboardzie webowym -
tu są tylko najważniejsze komendy na szybko, z poziomu Discorda.
"""
import discord
from discord import app_commands
from discord.ext import commands

from utils.player import resolve_playlist_queries, LavalinkUnavailableError, EQ_PRESETS


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _get_user_voice_channel(self, interaction: discord.Interaction):
        if interaction.user.voice and interaction.user.voice.channel:
            return interaction.user.voice.channel
        return None

    @app_commands.command(name="graj", description="Dogrywa utwór do kolejki (nazwa, link YouTube albo bezpośredni link do pliku audio)")
    @app_commands.describe(zapytanie="Tytuł, link YouTube albo bezpośredni link do pliku audio (mp3 itp.)")
    async def graj(self, interaction: discord.Interaction, zapytanie: str):
        await interaction.response.defer()
        channel = await self._get_user_voice_channel(interaction)
        if channel is None:
            await interaction.followup.send("Musisz najpierw wejść na kanał głosowy.")
            return

        try:
            player = await self.bot.players.connect(channel)
        except Exception as e:
            await interaction.followup.send(f"Nie mogę połączyć się z serwerem muzycznym (Lavalink). Błąd: {e}")
            return
        player.text_channel = interaction.channel

        player.add_to_queue(zapytanie)
        await interaction.followup.send(f"Dodano do kolejki: **{zapytanie}** 🎵")
        try:
            await player.start_if_idle()
        except LavalinkUnavailableError:
            pass

    @app_commands.command(name="nastepny", description="Odtwarza wybrany utwór NATYCHMIAST, z pominięciem kolejki")
    @app_commands.describe(zapytanie="Tytuł, link YouTube albo bezpośredni link do pliku audio")
    async def nastepny(self, interaction: discord.Interaction, zapytanie: str):
        await interaction.response.defer()
        player = self.bot.players.get(interaction.guild_id)
        if not player:
            channel = await self._get_user_voice_channel(interaction)
            if channel is None:
                await interaction.followup.send("Musisz najpierw wejść na kanał głosowy.")
                return
            player = await self.bot.players.connect(channel)
            player.text_channel = interaction.channel

        try:
            ok = await player.play_now(zapytanie)
        except LavalinkUnavailableError:
            await interaction.followup.send("⚠️ Serwer muzyczny (Lavalink) jest chwilowo niedostępny.")
            return
        if not ok:
            await interaction.followup.send("Nie udało się znaleźć tego utworu.")
            return
        await interaction.followup.send(f"▶️ Gram teraz: **{zapytanie}** (kolejka wznowi się zaraz po)")

    @app_commands.command(name="pomin", description="Pomija aktualnie grany utwór")
    async def pomin(self, interaction: discord.Interaction):
        player = self.bot.players.get(interaction.guild_id)
        if not player or not player.playing:
            await interaction.response.send_message("Nic teraz nie gra.")
            return
        await player.skip()
        await interaction.response.send_message("Pominięto utwór. ⏭️")

    @app_commands.command(name="stop", description="Zatrzymuje granie na chwilę (domyślnie 1 minutę), potem wznawia samo")
    @app_commands.describe(minuty="Na ile minut zatrzymać granie (domyślnie 1)")
    async def stop(self, interaction: discord.Interaction, minuty: float = 1.0):
        player = self.bot.players.get(interaction.guild_id)
        if not player:
            await interaction.response.send_message("Nie jestem połączony z żadnym kanałem.")
            return
        minuty = max(0.1, min(180, minuty))
        await player.pause_for(minuty)
        await interaction.response.send_message(f"⏸️ Zatrzymano na {minuty:g} min - wznowię automatycznie.")

    @app_commands.command(name="wznow", description="Wznawia granie (anuluje tymczasową pauzę)")
    async def wznow(self, interaction: discord.Interaction):
        player = self.bot.players.get(interaction.guild_id)
        if not player:
            await interaction.response.send_message("Nie jestem połączony z żadnym kanałem.")
            return
        await player.resume_now()
        await interaction.response.send_message("▶️ Wznowiono.")

    @app_commands.command(name="glosnosc", description="Ustawia głośność (0-150, gdzie 100 = normalna)")
    @app_commands.describe(procent="Głośność w procentach (0-150)")
    async def glosnosc(self, interaction: discord.Interaction, procent: int):
        player = self.bot.players.get(interaction.guild_id)
        if not player:
            await interaction.response.send_message("Nie jestem połączony z żadnym kanałem.")
            return
        procent = max(0, min(150, procent))
        await player.set_volume(procent)
        await self.bot.db.set_volume(interaction.guild_id, procent)
        await interaction.response.send_message(f"🔊 Głośność ustawiona na {procent}%.")

    @app_commands.command(name="eq", description="Ustawia equalizer")
    @app_commands.choices(preset=[app_commands.Choice(name=p, value=p) for p in EQ_PRESETS])
    async def eq(self, interaction: discord.Interaction, preset: app_commands.Choice[str]):
        player = self.bot.players.get(interaction.guild_id)
        if not player:
            await interaction.response.send_message("Nie jestem połączony z żadnym kanałem.")
            return
        await player.apply_eq_preset(preset.value)
        await self.bot.db.set_eq_preset(interaction.guild_id, preset.value)
        await interaction.response.send_message(f"🎚️ Equalizer ustawiony na: **{preset.value}**.")

    @app_commands.command(name="kolejka", description="Pokazuje aktualną kolejkę utworów")
    async def kolejka(self, interaction: discord.Interaction):
        player = self.bot.players.get(interaction.guild_id)
        lines = []
        if player and player.now_playing:
            lines.append(f"**Teraz gra:** {player.now_playing.title}")
        if player and player.query_queue:
            upcoming = player.query_queue[:10]
            lines.append("\n**Następne:**")
            lines.extend(f"{i+1}. {q}" for i, q in enumerate(upcoming))
            if len(player.query_queue) > 10:
                lines.append(f"...i {len(player.query_queue) - 10} więcej")
        if not lines:
            lines = ["Kolejka jest pusta."]
        await interaction.response.send_message("\n".join(lines))

    @app_commands.command(name="rozlacz", description="Rozłącza bota z kanału głosowego i wyłącza radio")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def rozlacz(self, interaction: discord.Interaction):
        player = self.bot.players.get(interaction.guild_id)
        if not player:
            await interaction.response.send_message("Nie jestem połączony z żadnym kanałem.")
            return
        await self.bot.db.set_radio_enabled(interaction.guild_id, False)
        await player.leave()
        await interaction.response.send_message("Rozłączono. 👋")


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
