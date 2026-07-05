"""
Sistema simples de níveis (XP), no estilo MEE6: XP por mensagem (com cooldown
para evitar spam), fórmula de nível progressiva, aviso de level-up e
comandos /rank e /leaderboard.
"""

from __future__ import annotations

import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import COR_EMBED
from utils.json_store import JsonStore
from utils.logger import get_logger

log = get_logger(__name__)

XP_MIN_POR_MENSAGEM = 8
XP_MAX_POR_MENSAGEM = 15
COOLDOWN_XP_SEGUNDOS = 60

xp_store = JsonStore("xp.json", padrao_item={"xp": 0, "nivel": 0})


def xp_para_nivel(nivel: int) -> int:
    """XP total acumulado necessário para alcançar um nível (curva progressiva)."""
    return 5 * (nivel ** 2) + 50 * nivel + 100


def nivel_a_partir_de_xp(xp: int) -> int:
    nivel = 0
    while xp >= xp_para_nivel(nivel + 1):
        nivel += 1
    return nivel


class Leveling(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._ultimo_xp_em: dict[str, float] = {}  # "guild_id:user_id" -> timestamp

    @staticmethod
    def _chave(guild_id: int, user_id: int) -> str:
        return f"{guild_id}:{user_id}"

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        chave = self._chave(message.guild.id, message.author.id)
        agora = time.monotonic()
        if agora - self._ultimo_xp_em.get(chave, 0) < COOLDOWN_XP_SEGUNDOS:
            return
        self._ultimo_xp_em[chave] = agora

        ganho = random.randint(XP_MIN_POR_MENSAGEM, XP_MAX_POR_MENSAGEM)
        item = await xp_store.incrementar(chave, "xp", ganho)
        novo_nivel = nivel_a_partir_de_xp(item["xp"])

        if novo_nivel > item.get("nivel", 0):
            await xp_store.set(chave, nivel=novo_nivel)
            embed = discord.Embed(
                description=f"🎉 {message.author.mention} subiu para o **nível {novo_nivel}**!",
                color=COR_EMBED,
            )
            try:
                await message.channel.send(embed=embed)
            except discord.HTTPException:
                pass

    @app_commands.command(name="rank", description="Mostra seu nível e XP no servidor")
    @app_commands.describe(usuario="Ver o rank de outra pessoa (opcional)")
    async def rank(self, interaction: discord.Interaction, usuario: discord.Member | None = None):
        alvo = usuario or interaction.user
        item = xp_store.get(self._chave(interaction.guild.id, alvo.id))
        nivel = nivel_a_partir_de_xp(item["xp"])
        xp_atual_nivel = item["xp"] - (xp_para_nivel(nivel) if nivel > 0 else 0)
        xp_necessario = xp_para_nivel(nivel + 1) - (xp_para_nivel(nivel) if nivel > 0 else 0)

        embed = discord.Embed(title=f"📊 Rank de {alvo.display_name}", color=COR_EMBED)
        embed.set_thumbnail(url=alvo.display_avatar.url)
        embed.add_field(name="Nível", value=str(nivel), inline=True)
        embed.add_field(name="XP total", value=str(item["xp"]), inline=True)
        embed.add_field(name="Progresso", value=f"{xp_atual_nivel}/{xp_necessario} XP", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Mostra o ranking de XP do servidor")
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        prefixo = f"{interaction.guild.id}:"
        topo = [(k, v) for k, v in xp_store.top(n=200, campo_ordenacao="xp") if k.startswith(prefixo)][:10]

        if not topo:
            await interaction.followup.send("Ainda não há ninguém no ranking deste servidor.")
            return

        linhas = []
        for i, (chave, item) in enumerate(topo, start=1):
            user_id = int(chave.split(":")[1])
            membro = interaction.guild.get_member(user_id)
            nome = membro.display_name if membro else f"Usuário {user_id}"
            nivel = nivel_a_partir_de_xp(item["xp"])
            linhas.append(f"`{i}.` **{nome}** — nível {nivel} ({item['xp']} XP)")

        embed = discord.Embed(title="🏆 Ranking do servidor", description="\n".join(linhas), color=COR_EMBED)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))
