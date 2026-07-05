"""
Núcleo do sistema de música: GuildPlayer (estado por servidor) e PlayerManager
(orquestra tudo). Toda ação que pode ser disparada por slash command, botão do
Discord OU pelo painel web passa por aqui — ponto único da verdade, sem lógica
duplicada entre as três interfaces (esse era um dos problemas do código original).

Suporta: fila, loop (desativado/música/fila), shuffle, vote-skip, volume,
cache de busca (via ytdlp_service), conversão de links do Spotify, e notifica
"observadores" (usado pelo painel web via WebSocket) sempre que o estado muda.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections import deque
from typing import Awaitable, Callable

import discord

from services.spotify_service import spotify_service
from services.ytdlp_service import FFMPEG_OPTS, ytdlp_service
from utils.errors import BuscaFalhouError, NadaTocandoError, NaoConectadoError
from utils.logger import get_logger

log = get_logger(__name__)

TEMPO_OCIOSO_SEGUNDOS = 300  # desconecta se ficar 5 min sem tocar nada
LOOP_MODOS = ("off", "track", "queue")

Callback = Callable[[int], Awaitable[None]]


class GuildPlayer:
    """Estado de reprodução de um único servidor."""

    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self.queue: deque[dict] = deque()
        self.voice_client: discord.VoiceClient | None = None
        self.atual: dict | None = None
        self.loop_mode: str = "off"
        self.volume: float = 0.5
        self.text_channel: discord.abc.Messageable | None = None
        self.now_playing_msg: discord.Message | None = None
        self.skip_votes: set[int] = set()
        self.ultimo_canal_voz_id: int | None = None
        self.parado_manualmente = False
        self.iniciado_em: float | None = None  # timestamp de quando a faixa atual começou
        self.pausado_em: float | None = None
        self.tempo_pausado_acumulado: float = 0.0
        self._tarefa_ociosa: asyncio.Task | None = None
        self._tarefa_canal_vazio: asyncio.Task | None = None

    def posicao_atual_segundos(self) -> float:
        if not self.iniciado_em or not self.atual:
            return 0.0
        if self.pausado_em:
            return max(0.0, self.pausado_em - self.iniciado_em - self.tempo_pausado_acumulado)
        return max(0.0, time.monotonic() - self.iniciado_em - self.tempo_pausado_acumulado)


class PlayerManager:
    def __init__(self):
        self.bot: discord.Client | None = None
        self._players: dict[int, GuildPlayer] = {}
        self._observadores: dict[int, list[Callback]] = {}

    def ligar_bot(self, bot: discord.Client) -> None:
        self.bot = bot

    def get(self, guild_id: int) -> GuildPlayer:
        if guild_id not in self._players:
            self._players[guild_id] = GuildPlayer(guild_id)
        return self._players[guild_id]

    def guild_ids_ativos(self) -> list[int]:
        return list(self._players.keys())

    # ---------- Observadores (usado pelo painel web via WebSocket) ----------

    def observar(self, guild_id: int, callback: Callback) -> None:
        self._observadores.setdefault(guild_id, []).append(callback)

    def parar_de_observar(self, guild_id: int, callback: Callback) -> None:
        lista = self._observadores.get(guild_id, [])
        if callback in lista:
            lista.remove(callback)

    def _notificar(self, guild_id: int) -> None:
        callbacks = list(self._observadores.get(guild_id, []))
        if not callbacks:
            return
        for cb in callbacks:
            asyncio.create_task(self._chamar_seguro(cb, guild_id))

    @staticmethod
    async def _chamar_seguro(cb: Callback, guild_id: int) -> None:
        try:
            await cb(guild_id)
        except Exception:  # noqa: BLE001
            log.exception("Erro ao notificar observador do player (guild %s)", guild_id)

    # ---------- Status (usado por /fila, painel de botões e painel web) ----------

    def status(self, guild: discord.Guild) -> dict:
        player = self.get(guild.id)
        pausado = bool(player.voice_client and player.voice_client.is_paused())
        tocando = bool(player.voice_client and player.voice_client.is_playing())
        return {
            "servidor": guild.name,
            "servidor_id": str(guild.id),
            "atual": _serializar_faixa(player.atual),
            "posicao": round(player.posicao_atual_segundos(), 1),
            "tocando": tocando,
            "pausado": pausado,
            "loop_mode": player.loop_mode,
            "volume": player.volume,
            "canal_voz": player.voice_client.channel.name if player.voice_client and player.voice_client.channel else None,
            "fila": [_serializar_faixa(m) for m in list(player.queue)[:50]],
        }

    # ---------- Conexão / reprodução ----------

    async def conectar(self, guild: discord.Guild, canal_voz: discord.VoiceChannel, text_channel) -> GuildPlayer:
        player = self.get(guild.id)
        player.text_channel = text_channel
        player.ultimo_canal_voz_id = canal_voz.id
        player.parado_manualmente = False

        if not player.voice_client or not player.voice_client.is_connected():
            player.voice_client = await canal_voz.connect(reconnect=True, timeout=15)
        elif player.voice_client.channel.id != canal_voz.id:
            await player.voice_client.move_to(canal_voz)
        return player

    async def adicionar_e_tocar(
        self,
        guild: discord.Guild,
        canal_voz: discord.VoiceChannel,
        text_channel,
        busca: str,
        requester: discord.Member,
    ) -> dict:
        if not canal_voz:
            raise NaoConectadoError()

        player = await self.conectar(guild, canal_voz, text_channel)

        # Spotify -> converte em 1+ queries de texto, cada uma resolvida via yt-dlp
        if spotify_service.eh_link_spotify(busca):
            queries = await spotify_service.resolver_queries(busca)
            if not queries:
                raise BuscaFalhouError("não encontrei faixas nesse link do Spotify.")
            primeira, *resto = queries
            faixas = await ytdlp_service.buscar(primeira)
            faixa = faixas[0]
            faixa["requester"] = requester
            player.queue.append(faixa)
            adicionadas = 1
            # o restante da playlist do Spotify é resolvido em segundo plano para não travar o comando
            if resto:
                asyncio.create_task(self._resolver_resto_spotify(player, resto, requester))
                adicionadas = f"{1} (+{len(resto)} sendo processadas em segundo plano)"
        else:
            faixas = await ytdlp_service.buscar(busca)
            for f in faixas:
                f["requester"] = requester
            player.queue.extend(faixas)
            adicionadas = len(faixas)
            faixa = faixas[0]

        estava_tocando = player.voice_client.is_playing() or player.voice_client.is_paused()
        if not estava_tocando:
            await self._tocar_proxima(guild)

        self._notificar(guild.id)
        return {
            "ok": True,
            "faixa": faixa,
            "adicionadas": adicionadas,
            "ja_tocando": estava_tocando,
        }

    async def _resolver_resto_spotify(self, player: GuildPlayer, queries: list[str], requester) -> None:
        for q in queries:
            try:
                faixas = await ytdlp_service.buscar(q)
                faixas[0]["requester"] = requester
                player.queue.append(faixas[0])
                self._notificar(player.guild_id)
            except BuscaFalhouError:
                continue
            await asyncio.sleep(0.3)  # evita rajada de requisições

    async def _tocar_proxima(self, guild: discord.Guild) -> None:
        player = self.get(guild.id)
        self._cancelar_tarefa_ociosa(player)
        player.skip_votes.clear()

        if player.loop_mode == "track" and player.atual:
            player.queue.appendleft(player.atual)
        elif player.loop_mode == "queue" and player.atual:
            player.queue.append(player.atual)

        if not player.queue:
            player.atual = None
            player.iniciado_em = None
            self._agendar_desconexao_ociosa(guild, player)
            asyncio.create_task(self._atualizar_painel(guild))
            self._notificar(guild.id)
            return

        proxima = player.queue.popleft()
        try:
            stream_url = await ytdlp_service.resolver_stream(proxima)
        except BuscaFalhouError as e:
            if player.text_channel:
                asyncio.create_task(player.text_channel.send(f"⚠️ Pulei **{proxima['title']}**: {e}"))
            asyncio.create_task(self._tocar_proxima(guild))
            return

        player.atual = proxima
        player.iniciado_em = time.monotonic()
        player.pausado_em = None
        player.tempo_pausado_acumulado = 0.0

        fonte_bruta = discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTS)
        fonte = discord.PCMVolumeTransformer(fonte_bruta, volume=player.volume)

        def _depois(erro: Exception | None):
            if erro:
                log.error("Erro durante a reprodução em '%s': %s", guild.name, erro)
            self.bot.loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self._tocar_proxima(guild))
            )

        if player.voice_client and player.voice_client.is_connected():
            player.voice_client.play(fonte, after=_depois)
            asyncio.create_task(self._atualizar_ou_criar_painel(guild))
        self._notificar(guild.id)

    async def _atualizar_ou_criar_painel(self, guild: discord.Guild) -> None:
        """Edita a mensagem 'tocando agora' existente; só cria uma nova se não houver uma."""
        from utils.helpers import embed_now_playing
        from cogs.music import ControlesMusica

        player = self.get(guild.id)
        embed = embed_now_playing(player, player.posicao_atual_segundos())

        if player.now_playing_msg:
            try:
                await player.now_playing_msg.edit(embed=embed, view=ControlesMusica())
                return
            except discord.NotFound:
                player.now_playing_msg = None
            except discord.HTTPException:
                pass

        if player.text_channel:
            try:
                player.now_playing_msg = await player.text_channel.send(embed=embed, view=ControlesMusica())
            except discord.HTTPException:
                player.now_playing_msg = None

    async def _atualizar_painel(self, guild: discord.Guild) -> None:
        from utils.helpers import embed_now_playing  # import tardio evita import circular

        player = self.get(guild.id)
        if not player.now_playing_msg:
            return
        try:
            from cogs.music import ControlesMusica  # import tardio (view)
            await player.now_playing_msg.edit(
                embed=embed_now_playing(player, player.posicao_atual_segundos()),
                view=ControlesMusica(),
            )
        except discord.NotFound:
            player.now_playing_msg = None
        except discord.HTTPException:
            pass

    # ---------- Ações compartilhadas (slash commands + botões + painel web) ----------

    async def pausar_continuar(self, guild: discord.Guild) -> dict:
        player = self.get(guild.id)
        if not player.voice_client:
            raise NadaTocandoError()
        if player.voice_client.is_playing():
            player.voice_client.pause()
            player.pausado_em = time.monotonic()
            asyncio.create_task(self._atualizar_painel(guild))
            self._notificar(guild.id)
            return {"ok": True, "mensagem": "⏸️ Pausado."}
        if player.voice_client.is_paused():
            if player.pausado_em:
                player.tempo_pausado_acumulado += time.monotonic() - player.pausado_em
            player.pausado_em = None
            player.voice_client.resume()
            asyncio.create_task(self._atualizar_painel(guild))
            self._notificar(guild.id)
            return {"ok": True, "mensagem": "▶️ Retomado."}
        raise NadaTocandoError()

    async def pular(self, guild: discord.Guild, solicitante: discord.Member | None = None, forcar: bool = False) -> dict:
        player = self.get(guild.id)
        if not player.voice_client or not (player.voice_client.is_playing() or player.voice_client.is_paused()):
            raise NadaTocandoError()

        if forcar or solicitante is None:
            player.voice_client.stop()
            self._notificar(guild.id)
            return {"ok": True, "mensagem": "⏭️ Música pulada."}

        from utils.permissions import humanos_no_canal, pode_agir_sem_votacao

        canal_voz = player.voice_client.channel
        if pode_agir_sem_votacao(solicitante, canal_voz):
            player.voice_client.stop()
            self._notificar(guild.id)
            return {"ok": True, "mensagem": "⏭️ Música pulada."}

        humanos = humanos_no_canal(canal_voz) if canal_voz else []
        player.skip_votes.add(solicitante.id)
        necessarios = max(1, (len(humanos) // 2) + 1)
        if len(player.skip_votes) >= necessarios:
            player.voice_client.stop()
            self._notificar(guild.id)
            return {"ok": True, "mensagem": f"⏭️ Votação concluída ({len(player.skip_votes)}/{necessarios}). Música pulada."}

        self._notificar(guild.id)
        return {
            "ok": True,
            "mensagem": f"🗳️ Voto registrado ({len(player.skip_votes)}/{necessarios} necessários para pular).",
        }

    async def parar(self, guild: discord.Guild) -> dict:
        player = self.get(guild.id)
        player.queue.clear()
        player.atual = None
        player.parado_manualmente = True
        player.skip_votes.clear()
        self._cancelar_tarefa_ociosa(player)
        if player.voice_client:
            await player.voice_client.disconnect(force=True)
            player.voice_client = None
        if player.now_playing_msg:
            try:
                await player.now_playing_msg.delete()
            except discord.HTTPException:
                pass
            player.now_playing_msg = None
        self._notificar(guild.id)
        return {"ok": True, "mensagem": "⏹️ Parado e desconectado."}

    async def alternar_loop(self, guild: discord.Guild, modo: str | None = None) -> dict:
        player = self.get(guild.id)
        if modo and modo in LOOP_MODOS:
            player.loop_mode = modo
        else:
            atual_idx = LOOP_MODOS.index(player.loop_mode)
            player.loop_mode = LOOP_MODOS[(atual_idx + 1) % len(LOOP_MODOS)]
        textos = {"off": "Loop desativado.", "track": "🔂 Loop da música atual ativado.", "queue": "🔁 Loop da fila ativado."}
        self._notificar(guild.id)
        return {"ok": True, "mensagem": textos[player.loop_mode], "loop_mode": player.loop_mode}

    async def embaralhar(self, guild: discord.Guild) -> dict:
        player = self.get(guild.id)
        if len(player.queue) < 2:
            return {"ok": False, "mensagem": "Não há músicas suficientes na fila para embaralhar."}
        itens = list(player.queue)
        random.shuffle(itens)
        player.queue = deque(itens)
        self._notificar(guild.id)
        return {"ok": True, "mensagem": f"🔀 Fila embaralhada ({len(itens)} músicas)."}

    async def definir_volume(self, guild: discord.Guild, volume_percentual: int) -> dict:
        player = self.get(guild.id)
        volume_percentual = max(0, min(150, volume_percentual))
        player.volume = volume_percentual / 100
        if player.voice_client and isinstance(player.voice_client.source, discord.PCMVolumeTransformer):
            player.voice_client.source.volume = player.volume
        self._notificar(guild.id)
        return {"ok": True, "mensagem": f"🔊 Volume ajustado para {volume_percentual}%."}

    async def remover_da_fila(self, guild: discord.Guild, posicao: int) -> dict:
        player = self.get(guild.id)
        if posicao < 1 or posicao > len(player.queue):
            return {"ok": False, "mensagem": "Posição inválida."}
        itens = list(player.queue)
        removida = itens.pop(posicao - 1)
        player.queue = deque(itens)
        self._notificar(guild.id)
        return {"ok": True, "mensagem": f"🗑️ Removido: **{removida['title']}**."}

    # ---------- Auto-desconexão por inatividade / canal vazio ----------

    def _agendar_desconexao_ociosa(self, guild: discord.Guild, player: GuildPlayer) -> None:
        self._cancelar_tarefa_ociosa(player)

        async def _tarefa():
            await asyncio.sleep(TEMPO_OCIOSO_SEGUNDOS)
            if player.voice_client and not player.atual and not player.queue:
                log.info("Desconectando de '%s' por inatividade.", guild.name)
                await self.parar(guild)

        player._tarefa_ociosa = asyncio.create_task(_tarefa())

    @staticmethod
    def _cancelar_tarefa_ociosa(player: GuildPlayer) -> None:
        if player._tarefa_ociosa and not player._tarefa_ociosa.done():
            player._tarefa_ociosa.cancel()
        player._tarefa_ociosa = None

    async def verificar_canal_vazio(self, guild: discord.Guild) -> None:
        """Chamado pelo evento on_voice_state_update. Desconecta após 60s sozinho no canal."""
        player = self.get(guild.id)
        if not player.voice_client or not player.voice_client.channel:
            return

        humanos = [m for m in player.voice_client.channel.members if not m.bot]
        if player._tarefa_canal_vazio and not player._tarefa_canal_vazio.done():
            player._tarefa_canal_vazio.cancel()
            player._tarefa_canal_vazio = None

        if humanos:
            return

        async def _tarefa():
            await asyncio.sleep(60)
            if player.voice_client and not [m for m in player.voice_client.channel.members if not m.bot]:
                log.info("Canal de voz vazio em '%s' — desconectando.", guild.name)
                await self.parar(guild)

        player._tarefa_canal_vazio = asyncio.create_task(_tarefa())

    async def tentar_reconectar(self, guild: discord.Guild) -> bool:
        """Tenta reconectar ao último canal de voz após uma queda inesperada de conexão."""
        player = self.get(guild.id)
        if player.parado_manualmente or not player.ultimo_canal_voz_id:
            return False
        if player.voice_client and player.voice_client.is_connected():
            return True

        canal = guild.get_channel(player.ultimo_canal_voz_id)
        if not canal:
            return False

        try:
            log.warning("Reconectando ao canal de voz '%s' em '%s'...", canal.name, guild.name)
            player.voice_client = await canal.connect(reconnect=True, timeout=15)
            if player.atual:
                # a stream anterior não é mais válida; resolve novamente e continua da mesma faixa
                player.queue.appendleft(player.atual)
                await self._tocar_proxima(guild)
            return True
        except discord.ClientException as e:
            log.error("Falha ao reconectar em '%s': %s", guild.name, e)
            return False


def _serializar_faixa(faixa: dict | None) -> dict | None:
    if not faixa:
        return None
    requester = faixa.get("requester")
    return {
        "title": faixa.get("title"),
        "webpage_url": faixa.get("webpage_url"),
        "thumbnail": faixa.get("thumbnail"),
        "duration": faixa.get("duration"),
        "uploader": faixa.get("uploader"),
        "requester": getattr(requester, "display_name", None) if requester else None,
    }


# Instância única compartilhada entre bot (cogs) e painel web (mesmo processo/loop)
player_manager = PlayerManager()
