"""
System uprawnień dla komend administracyjnych bota (nie mylić z uprawnieniami
Discorda). Serwer ustawia JEDNĄ rolę ("rola admina bota") komendą /rolaadmina,
i tylko osoby z tą rolą (albo z uprawnieniem Administrator) mogą potem używać
komend typu /autoplay24_7, /kanalpoziomow, /rolapoziom.

Dopóki rola nie zostanie ustawiona, tymi komendami mogą się posługiwać osoby
z uprawnieniem Discorda "Zarządzaj serwerem" (typowo świeżo dodany bot jeszcze
nie ma skonfigurowanej roli, więc potrzebny jest bezpieczny stan początkowy).
"""
import discord
from discord import app_commands


async def is_bot_admin(bot, member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    settings = await bot.db.get_settings(member.guild.id)
    role_id = settings.get("admin_role_id")
    if role_id:
        return any(role.id == role_id for role in member.roles)
    # Rola jeszcze nie ustawiona - awaryjnie honorujemy "Zarządzaj serwerem"
    return member.guild_permissions.manage_guild


class NotBotAdmin(app_commands.CheckFailure):
    pass


def bot_admin_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        allowed = await is_bot_admin(interaction.client, interaction.user)
        if not allowed:
            raise NotBotAdmin("Brak uprawnień do zarządzania botem na tym serwerze.")
        return True

    return app_commands.check(predicate)
