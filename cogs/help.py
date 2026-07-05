"""
Sistema de ajuda interativo: /ajuda mostra um menu (dropdown) de categorias;
escolher uma categoria edita a mesma mensagem com os comandos daquela seção.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import COR_EMBED

CATEGORIAS: dict[str, list[tuple[str, str]]] = {
    "🎵 Música": [
        ("/tocar <busca>", "Toca uma música/playlist (YouTube, Spotify ou nome) ou adiciona na fila"),
        ("/pular", "Pula a música atual (pode exigir votação)"),
        ("/pausar · /continuar", "Pausa/retoma a reprodução"),
        ("/parar", "Para tudo, limpa a fila e desconecta"),
        ("/fila", "Mostra a fila de músicas"),
        ("/loop", "Alterna entre: desativado → música atual → fila inteira"),
        ("/shuffle", "Embaralha a fila"),
        ("/volume <0-150>", "Ajusta o volume"),
        ("/remover <posição>", "Remove uma música específica da fila"),
        ("/painel", "Mostra o painel de botões de controle"),
    ],
    "⚙️ Configuração": [
        ("/dj <cargo>", "Define o cargo de DJ (pula/para sem votação) — requer Gerenciar Servidor"),
        ("/canal_musica <canal>", "Restringe comandos de música a um canal — requer Gerenciar Servidor"),
    ],
    "🏆 Níveis": [
        ("/rank", "Mostra seu nível e progresso de XP"),
        ("/leaderboard", "Ranking de XP do servidor"),
    ],
    "💰 Economia": [
        ("/saldo", "Mostra seu saldo de moedas"),
        ("/trabalhar", "Trabalhe para ganhar moedas (1x por hora)"),
        ("/transferir <usuário> <quantidade>", "Transfere moedas para outra pessoa"),
        ("/ranking_moedas", "Ranking de moedas do servidor"),
    ],
}


def _embed_categoria(nome: str) -> discord.Embed:
    embed = discord.Embed(title=f"Ajuda — {nome}", color=COR_EMBED)
    for comando, descricao in CATEGORIAS[nome]:
        embed.add_field(name=comando, value=descricao, inline=False)
    return embed


def _embed_inicial() -> discord.Embed:
    embed = discord.Embed(
        title="🎧 FlaviMusic — Central de Ajuda",
        description="Escolha uma categoria no menu abaixo para ver os comandos disponíveis.",
        color=COR_EMBED,
    )
    for nome in CATEGORIAS:
        embed.add_field(name=nome, value=f"{len(CATEGORIAS[nome])} comando(s)", inline=True)
    return embed


class MenuAjuda(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.select(
        placeholder="Escolha uma categoria...",
        options=[discord.SelectOption(label=nome, value=nome) for nome in CATEGORIAS],
    )
    async def selecionar(self, interaction: discord.Interaction, select: discord.ui.Select):
        nome = select.values[0]
        await interaction.response.edit_message(embed=_embed_categoria(nome), view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class Ajuda(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ajuda", description="Mostra a lista de comandos do FlaviMusic")
    async def ajuda(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=_embed_inicial(), view=MenuAjuda())


async def setup(bot: commands.Bot):
    await bot.add_cog(Ajuda(bot))
