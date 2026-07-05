"""
Cog de música: comandos slash + botões persistentes.

Toda a lógica de negócio (fila, loop, votação, etc.) vive em services/player.py
(PlayerManager). Este cog é só a "casca" que conecta comandos do Discord a essa
lógica — o mesmo PlayerManager também é usado pelo painel web (web/routers),
então uma ação feita no site aparece refletida aqui e vice-versa.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from services.player import player_manager
from utils.errors import NaoConectadoError
from utils.helpers import embed_erro, embed_faixa, embed_fila, embed_now_playing, embed_sucesso
from utils.logger import get_logger
from utils.permissions import canal_permitido

log = get_logger(__name__)

COOLDOWN_PADRAO = app_commands.checks.cooldown(1, 3.0, key=lambda i: (i.guild_id, i.user.id))


def _checar_canal():
    async def predicado(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return False
        if not canal_permitido(interaction.guild.id, interaction.channel.id):
            from utils.config_store import config_store

            cfg = config_store.get(interaction.guild.id)
            canal = interaction.guild.get_channel(cfg["canal_musica_id"])
            nome = canal.mention if canal else "o canal configurado"
            await interaction.response.send_message(
                embed=embed_erro("Canal errado", f"Use comandos de música em {nome}."), ephemeral=True
            )
            return False
        return True

    return app_commands.check(predicado)


class ControlesMusica(discord.ui.View):
    """Botões persistentes anexados à mensagem 'tocando agora' (sobrevivem a restart, custom_id fixo)."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(emoji="⏯️", style=discord.ButtonStyle.secondary, custom_id="flavimusic:playpause", row=0)
    async def playpause(self, interaction: discord.Interaction, button: discord.ui.Button):
        resultado = await player_manager.pausar_continuar(interaction.guild)
        await interaction.response.send_message(resultado["mensagem"], ephemeral=True)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, custom_id="flavimusic:skip", row=0)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        resultado = await player_manager.pular(interaction.guild, solicitante=interaction.user)
        await interaction.response.send_message(resultado["mensagem"], ephemeral=True)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, custom_id="flavimusic:loop", row=0)
    async def loop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        resultado = await player_manager.alternar_loop(interaction.guild)
        await interaction.response.send_message(resultado["mensagem"], ephemeral=True)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, custom_id="flavimusic:shuffle", row=0)
    async def shuffle_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        resultado = await player_manager.embaralhar(interaction.guild)
        await interaction.response.send_message(resultado["mensagem"], ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, custom_id="flavimusic:stop", row=0)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        resultado = await player_manager.parar(interaction.guild)
        await interaction.response.send_message(resultado["mensagem"], ephemeral=True)


class Musica(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        player_manager.ligar_bot(bot)

    async def cog_load(self):
        self.bot.add_view(ControlesMusica())

    # ---------- Slash commands ----------

    @app_commands.command(name="tocar", description="Toca uma música/playlist (YouTube, Spotify ou nome) ou adiciona na fila")
    @app_commands.describe(busca="Nome da música, link do YouTube ou link do Spotify")
    @_checar_canal()
    @COOLDOWN_PADRAO
    async def tocar(self, interaction: discord.Interaction, busca: str):
        await interaction.response.defer()

        if not interaction.user.voice or not interaction.user.voice.channel:
            raise NaoConectadoError()

        resultado = await player_manager.adicionar_e_tocar(
            interaction.guild, interaction.user.voice.channel, interaction.channel, busca, interaction.user
        )
        prefixo = "▶️ Tocando agora" if not resultado["ja_tocando"] else "🎶 Adicionado à fila"
        embed = embed_faixa(resultado["faixa"], titulo_prefixo=prefixo)
        if isinstance(resultado["adicionadas"], int) and resultado["adicionadas"] > 1:
            embed.add_field(name="Playlist", value=f"+{resultado['adicionadas'] - 1} música(s) adicionada(s)", inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="pular", description="Pula para a próxima música (pode exigir votação)")
    @_checar_canal()
    async def pular(self, interaction: discord.Interaction):
        resultado = await player_manager.pular(interaction.guild, solicitante=interaction.user)
        await interaction.response.send_message(resultado["mensagem"])

    @app_commands.command(name="pausar", description="Pausa a música atual")
    @_checar_canal()
    async def pausar(self, interaction: discord.Interaction):
        resultado = await player_manager.pausar_continuar(interaction.guild)
        await interaction.response.send_message(resultado["mensagem"])

    @app_commands.command(name="continuar", description="Retoma a música pausada")
    @_checar_canal()
    async def continuar(self, interaction: discord.Interaction):
        resultado = await player_manager.pausar_continuar(interaction.guild)
        await interaction.response.send_message(resultado["mensagem"])

    @app_commands.command(name="parar", description="Para a música, limpa a fila e desconecta")
    @_checar_canal()
    async def parar(self, interaction: discord.Interaction):
        resultado = await player_manager.parar(interaction.guild)
        await interaction.response.send_message(resultado["mensagem"])

    @app_commands.command(name="fila", description="Mostra a fila de músicas")
    async def fila(self, interaction: discord.Interaction):
        player = player_manager.get(interaction.guild.id)
        await interaction.response.send_message(embed=embed_fila(player))

    @app_commands.command(name="loop", description="Alterna o modo de loop: desativado → música → fila")
    @_checar_canal()
    async def loop_cmd(self, interaction: discord.Interaction):
        resultado = await player_manager.alternar_loop(interaction.guild)
        await interaction.response.send_message(resultado["mensagem"])

    @app_commands.command(name="shuffle", description="Embaralha a fila de músicas")
    @_checar_canal()
    async def shuffle(self, interaction: discord.Interaction):
        resultado = await player_manager.embaralhar(interaction.guild)
        await interaction.response.send_message(resultado["mensagem"])

    @app_commands.command(name="volume", description="Ajusta o volume (0 a 150%)")
    @app_commands.describe(percentual="Volume em porcentagem, ex: 80")
    @_checar_canal()
    async def volume(self, interaction: discord.Interaction, percentual: app_commands.Range[int, 0, 150]):
        resultado = await player_manager.definir_volume(interaction.guild, percentual)
        await interaction.response.send_message(resultado["mensagem"])

    @app_commands.command(name="remover", description="Remove uma música da fila pela posição")
    @app_commands.describe(posicao="Posição na fila (veja com /fila)")
    @_checar_canal()
    async def remover(self, interaction: discord.Interaction, posicao: int):
        resultado = await player_manager.remover_da_fila(interaction.guild, posicao)
        await interaction.response.send_message(resultado["mensagem"])

    @app_commands.command(name="painel", description="Mostra o painel de controle com botões")
    @_checar_canal()
    async def painel(self, interaction: discord.Interaction):
        player = player_manager.get(interaction.guild.id)
        player.text_channel = interaction.channel
        await interaction.response.send_message(
            embed=embed_now_playing(player, player.posicao_atual_segundos()), view=ControlesMusica()
        )
        player.now_playing_msg = await interaction.original_response()

    @app_commands.command(name="dj", description="Define o cargo de DJ (pode pular/parar sem votação)")
    @app_commands.describe(cargo="Cargo que terá poderes de DJ")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def dj(self, interaction: discord.Interaction, cargo: discord.Role):
        from utils.config_store import config_store

        await config_store.set(interaction.guild.id, dj_role_id=cargo.id)
        await interaction.response.send_message(
            embed=embed_sucesso("Cargo de DJ definido", f"{cargo.mention} agora pode usar comandos de DJ sem votação.")
        )

    @app_commands.command(name="canal_musica", description="Restringe comandos de música a um canal específico")
    @app_commands.describe(canal="Canal permitido (deixe vazio para liberar em qualquer canal)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def canal_musica(self, interaction: discord.Interaction, canal: discord.TextChannel | None = None):
        from utils.config_store import config_store

        await config_store.set(interaction.guild.id, canal_musica_id=canal.id if canal else None)
        if canal:
            msg = f"Comandos de música agora só funcionam em {canal.mention}."
        else:
            msg = "Comandos de música liberados em qualquer canal."
        await interaction.response.send_message(embed=embed_sucesso("Configuração salva", msg))


async def setup(bot: commands.Bot):
    await bot.add_cog(Musica(bot))
