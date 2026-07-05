"""
Sistema de economia simples: moeda virtual ("moedas"), trabalho com cooldown,
transferências entre usuários e ranking. Pensado como complemento leve ao
sistema de níveis — não é o foco do bot, então fica intencionalmente simples.
"""

from __future__ import annotations

import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import COR_EMBED, embed_erro
from utils.json_store import JsonStore
from utils.logger import get_logger

log = get_logger(__name__)

COOLDOWN_TRABALHAR_SEGUNDOS = 3600
GANHO_MIN_TRABALHO = 50
GANHO_MAX_TRABALHO = 200
SALDO_INICIAL = 100

economia_store = JsonStore("economia.json", padrao_item={"saldo": SALDO_INICIAL})

FRASES_TRABALHO = [
    "Você tocou música em um evento e recebeu",
    "Você ajudou a organizar um servidor e ganhou",
    "Você vendeu uma playlist exclusiva e faturou",
    "Você fez um freela de DJ e recebeu",
]


class Economia(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._ultimo_trabalho_em: dict[str, float] = {}

    @staticmethod
    def _chave(guild_id: int, user_id: int) -> str:
        return f"{guild_id}:{user_id}"

    @app_commands.command(name="saldo", description="Mostra seu saldo de moedas")
    @app_commands.describe(usuario="Ver o saldo de outra pessoa (opcional)")
    async def saldo(self, interaction: discord.Interaction, usuario: discord.Member | None = None):
        alvo = usuario or interaction.user
        item = economia_store.get(self._chave(interaction.guild.id, alvo.id))
        embed = discord.Embed(
            title=f"💰 Carteira de {alvo.display_name}",
            description=f"**{item['saldo']}** moedas",
            color=COR_EMBED,
        )
        embed.set_thumbnail(url=alvo.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="trabalhar", description="Trabalhe para ganhar moedas (1x por hora)")
    async def trabalhar(self, interaction: discord.Interaction):
        chave = self._chave(interaction.guild.id, interaction.user.id)
        agora = time.monotonic()
        restante = COOLDOWN_TRABALHAR_SEGUNDOS - (agora - self._ultimo_trabalho_em.get(chave, 0))
        if restante > 0:
            minutos = int(restante // 60)
            await interaction.response.send_message(
                embed=embed_erro("Ainda cansado", f"Você pode trabalhar novamente em {minutos} minuto(s)."),
                ephemeral=True,
            )
            return

        self._ultimo_trabalho_em[chave] = agora
        ganho = random.randint(GANHO_MIN_TRABALHO, GANHO_MAX_TRABALHO)
        frase = random.choice(FRASES_TRABALHO)
        item = await economia_store.incrementar(chave, "saldo", ganho)

        embed = discord.Embed(
            description=f"💼 {frase} **{ganho}** moedas!\nSaldo atual: **{item['saldo']}** moedas.",
            color=COR_EMBED,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="transferir", description="Transfere moedas para outra pessoa")
    @app_commands.describe(usuario="Quem vai receber", quantidade="Quantidade de moedas")
    async def transferir(self, interaction: discord.Interaction, usuario: discord.Member, quantidade: app_commands.Range[int, 1, None]):
        if usuario.id == interaction.user.id:
            await interaction.response.send_message(
                embed=embed_erro("Operação inválida", "Você não pode transferir moedas para si mesmo."), ephemeral=True
            )
            return

        chave_origem = self._chave(interaction.guild.id, interaction.user.id)
        origem = economia_store.get(chave_origem)
        if origem["saldo"] < quantidade:
            await interaction.response.send_message(
                embed=embed_erro("Saldo insuficiente", f"Você tem apenas {origem['saldo']} moedas."), ephemeral=True
            )
            return

        chave_destino = self._chave(interaction.guild.id, usuario.id)
        await economia_store.incrementar(chave_origem, "saldo", -quantidade)
        await economia_store.incrementar(chave_destino, "saldo", quantidade)

        embed = discord.Embed(
            description=f"💸 {interaction.user.mention} transferiu **{quantidade}** moedas para {usuario.mention}.",
            color=COR_EMBED,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ranking_moedas", description="Mostra o ranking de moedas do servidor")
    async def ranking_moedas(self, interaction: discord.Interaction):
        await interaction.response.defer()
        prefixo = f"{interaction.guild.id}:"
        topo = [(k, v) for k, v in economia_store.top(n=200, campo_ordenacao="saldo") if k.startswith(prefixo)][:10]

        if not topo:
            await interaction.followup.send("Ainda não há ninguém no ranking deste servidor.")
            return

        linhas = []
        for i, (chave, item) in enumerate(topo, start=1):
            user_id = int(chave.split(":")[1])
            membro = interaction.guild.get_member(user_id)
            nome = membro.display_name if membro else f"Usuário {user_id}"
            linhas.append(f"`{i}.` **{nome}** — {item['saldo']} moedas")

        embed = discord.Embed(title="🏆 Ranking de moedas", description="\n".join(linhas), color=COR_EMBED)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economia(bot))
