"""
Komendy muzyczne bota-radia.
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils.player import (
    LavalinkUnavailableError,
    EQ_PRESETS,
)


class Music(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot


    async def _get_user_voice_channel(
        self,
        interaction: discord.Interaction
    ):

        if interaction.user.voice:
            return interaction.user.voice.channel

        return None



    # =====================
    # PLAY
    # =====================

    @app_commands.command(
        name="graj",
        description="Odtwarza utwór z YouTube lub link audio"
    )
    async def graj(
        self,
        interaction: discord.Interaction,
        zapytanie: str
    ):

        await interaction.response.defer()


        channel = await self._get_user_voice_channel(
            interaction
        )


        if not channel:
            await interaction.followup.send(
                "❌ Wejdź najpierw na kanał głosowy."
            )
            return


        try:

            player = await self.bot.players.connect(
                channel
            )

        except Exception as e:

            await interaction.followup.send(
                f"❌ Lavalink nie działa:\n```{e}```"
            )
            return



        player.text_channel = interaction.channel


        player.add_to_queue(
            zapytanie
        )


        await interaction.followup.send(
            f"🎵 Dodano: **{zapytanie}**"
        )


        try:

            await player.start_if_idle()


        except LavalinkUnavailableError:

            await interaction.followup.send(
                "❌ Lavalink jest niedostępny."
            )



    # =====================
    # SKIP
    # =====================

    @app_commands.command(
        name="pomin",
        description="Pomija utwór"
    )
    async def pomin(
        self,
        interaction: discord.Interaction
    ):

        player = self.bot.players.get(
            interaction.guild_id
        )


        if not player or not player.playing:

            await interaction.response.send_message(
                "❌ Nic nie gra."
            )
            return


        await player.stop()


        await interaction.response.send_message(
            "⏭️ Pominięto."
        )



    # =====================
    # PAUSE
    # =====================

    @app_commands.command(
        name="stop",
        description="Pauzuje radio"
    )
    async def stop(
        self,
        interaction: discord.Interaction,
        minuty: float = 1
    ):

        player = self.bot.players.get(
            interaction.guild_id
        )


        if not player:

            await interaction.response.send_message(
                "❌ Bot nie gra."
            )
            return


        minuty = max(
            0.1,
            min(
                180,
                minuty
            )
        )


        await player.pause_for(
            minuty
        )


        await interaction.response.send_message(
            f"⏸️ Pauza {minuty:g} min."
        )



    @app_commands.command(
        name="wznow",
        description="Wznawia muzykę"
    )
    async def wznow(
        self,
        interaction: discord.Interaction
    ):

        player = self.bot.players.get(
            interaction.guild_id
        )


        if not player:

            await interaction.response.send_message(
                "❌ Brak odtwarzacza."
            )
            return


        await player.resume_now()


        await interaction.response.send_message(
            "▶️ Wznowiono."
        )



    # =====================
    # VOLUME
    # =====================

    @app_commands.command(
        name="glosnosc",
        description="Ustawia głośność"
    )
    async def glosnosc(
        self,
        interaction: discord.Interaction,
        procent: int
    ):


        player = self.bot.players.get(
            interaction.guild_id
        )


        if not player:

            await interaction.response.send_message(
                "❌ Brak muzyki."
            )
            return


        procent = max(
            0,
            min(
                150,
                procent
            )
        )


        await player.set_volume(
            procent
        )


        await interaction.response.send_message(
            f"🔊 Głośność: {procent}%"
        )



    # =====================
    # EQ
    # =====================

    @app_commands.command(
        name="eq",
        description="Equalizer"
    )
    @app_commands.choices(
        preset=[
            app_commands.Choice(
                name=x,
                value=x
            )
            for x in EQ_PRESETS
        ]
    )
    async def eq(
        self,
        interaction: discord.Interaction,
        preset: app_commands.Choice[str]
    ):


        player = self.bot.players.get(
            interaction.guild_id
        )


        if not player:

            await interaction.response.send_message(
                "❌ Brak muzyki."
            )
            return



        await player.apply_eq_preset(
            preset.value
        )


        await interaction.response.send_message(
            f"🎚️ EQ: **{preset.value}**"
        )



    # =====================
    # QUEUE
    # =====================

    @app_commands.command(
        name="kolejka",
        description="Pokazuje kolejkę"
    )
    async def kolejka(
        self,
        interaction: discord.Interaction
    ):


        player = self.bot.players.get(
            interaction.guild_id
        )


        if not player:

            await interaction.response.send_message(
                "📭 Kolejka pusta."
            )
            return



        text = []


        if player.now_playing:

            text.append(
                f"🎵 Teraz: {player.now_playing.title}"
            )



        for i, q in enumerate(
            player.query_queue[:10],
            1
        ):

            text.append(
                f"{i}. {q}"
            )



        await interaction.response.send_message(
            "\n".join(text)
            if text
            else "📭 Pusto"
        )



    # =====================
    # DISCONNECT
    # =====================

    @app_commands.command(
        name="rozlacz",
        description="Rozłącza radio"
    )
    async def rozlacz(
        self,
        interaction: discord.Interaction
    ):


        player = self.bot.players.get(
            interaction.guild_id
        )


        if not player:

            await interaction.response.send_message(
                "❌ Nie jestem na kanale."
            )
            return



        await player.leave()


        await interaction.response.send_message(
            "👋 Rozłączono."
        )



async def setup(bot: commands.Bot):

    await bot.add_cog(
        Music(bot)
    )
