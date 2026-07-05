"""
Funções utilitárias compartilhadas: formatação de duração, montagem de embeds
e barra de progresso usadas pelos cogs de música.
"""

from __future__ import annotations

import discord

COR_EMBED = 0xE8A33D
COR_ERRO = 0xD9635A
COR_SUCESSO = 0x4FD1C5


def formatar_duracao(segundos: int | float | None) -> str:
    """Converte segundos em 'MM:SS' ou 'HH:MM:SS'. Retorna 'LIVE' para lives (duração None/0)."""
    if not segundos:
        return "🔴 LIVE"
    segundos = int(segundos)
    h, resto = divmod(segundos, 3600)
    m, s = divmod(resto, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def barra_progresso(posicao: float, duracao: float, tamanho: int = 20) -> str:
    """Gera uma barra de progresso textual: ex '▬▬▬🔘▬▬▬▬▬▬▬▬'."""
    if not duracao:
        return "▬" * tamanho
    proporcao = max(0.0, min(1.0, posicao / duracao))
    pos = int(proporcao * tamanho)
    pos = max(0, min(tamanho - 1, pos))
    return "▬" * pos + "🔘" + "▬" * (tamanho - pos - 1)


def embed_erro(titulo: str, descricao: str = "") -> discord.Embed:
    return discord.Embed(title=f"⚠️ {titulo}", description=descricao or None, color=COR_ERRO)


def embed_sucesso(titulo: str, descricao: str = "") -> discord.Embed:
    return discord.Embed(title=f"✅ {titulo}", description=descricao or None, color=COR_SUCESSO)


def embed_faixa(faixa: dict, titulo_prefixo: str = "🎶 Adicionado à fila") -> discord.Embed:
    """Monta um embed rico para uma faixa: thumbnail, duração, autor do pedido, fonte."""
    embed = discord.Embed(
        title=titulo_prefixo,
        description=f"[{faixa['title']}]({faixa.get('webpage_url', '')})",
        color=COR_EMBED,
    )
    if faixa.get("thumbnail"):
        embed.set_thumbnail(url=faixa["thumbnail"])
    embed.add_field(name="Duração", value=formatar_duracao(faixa.get("duration")), inline=True)
    if faixa.get("uploader"):
        embed.add_field(name="Canal", value=faixa["uploader"], inline=True)
    requester = faixa.get("requester")
    if requester:
        nome = getattr(requester, "display_name", str(requester))
        embed.set_footer(text=f"Pedido por {nome}", icon_url=getattr(requester, "display_avatar", None) and requester.display_avatar.url)
    return embed


def embed_now_playing(player, posicao_segundos: float = 0) -> discord.Embed:
    """Embed completo de 'tocando agora', usado no painel de botões e no painel web."""
    if not player.atual:
        embed = discord.Embed(title="⏹️ Nada tocando", description="Use `/tocar` para começar.", color=COR_EMBED)
        return embed

    faixa = player.atual
    pausado = bool(player.voice_client and player.voice_client.is_paused())
    estado = "⏸️ Pausado" if pausado else "▶️ Tocando agora"

    embed = discord.Embed(
        title=estado,
        description=f"**[{faixa['title']}]({faixa.get('webpage_url', '')})**",
        color=COR_EMBED,
    )
    if faixa.get("thumbnail"):
        embed.set_thumbnail(url=faixa["thumbnail"])

    duracao = faixa.get("duration") or 0
    embed.add_field(
        name="Progresso",
        value=f"`{formatar_duracao(posicao_segundos)}` {barra_progresso(posicao_segundos, duracao)} `{formatar_duracao(duracao)}`",
        inline=False,
    )

    mapa_loop = {"off": "Desativado", "track": "🔂 Música atual", "queue": "🔁 Fila inteira"}
    embed.add_field(name="Loop", value=mapa_loop.get(player.loop_mode, "Desativado"), inline=True)
    embed.add_field(name="Na fila", value=str(len(player.queue)), inline=True)
    embed.add_field(name="Volume", value=f"{int(player.volume * 100)}%", inline=True)

    requester = faixa.get("requester")
    if requester:
        nome = getattr(requester, "display_name", str(requester))
        avatar = getattr(requester, "display_avatar", None)
        embed.set_footer(text=f"Pedido por {nome}", icon_url=avatar.url if avatar else None)

    return embed


def embed_fila(player, pagina: int = 0, por_pagina: int = 10) -> discord.Embed:
    """Embed paginado da fila de músicas."""
    itens = list(player.queue)
    embed = discord.Embed(title="🎼 Fila de músicas", color=COR_EMBED)

    if player.atual:
        embed.add_field(
            name="Tocando agora",
            value=f"**{player.atual['title']}** · {formatar_duracao(player.atual.get('duration'))}",
            inline=False,
        )

    if not itens:
        embed.add_field(name="Próximas", value="_A fila está vazia._", inline=False)
        return embed

    inicio = pagina * por_pagina
    pedaco = itens[inicio: inicio + por_pagina]
    linhas = []
    for i, musica in enumerate(pedaco, start=inicio + 1):
        duracao = formatar_duracao(musica.get("duration"))
        requester = musica.get("requester")
        nome_req = f" · _{getattr(requester, 'display_name', requester)}_" if requester else ""
        linhas.append(f"`{i}.` {musica['title']} — `{duracao}`{nome_req}")

    embed.add_field(name="Próximas", value="\n".join(linhas), inline=False)
    total_paginas = max(1, -(-len(itens) // por_pagina))
    duracao_total = sum(m.get("duration") or 0 for m in itens)
    embed.set_footer(text=f"Página {pagina + 1}/{total_paginas} · {len(itens)} música(s) · {formatar_duracao(duracao_total)} restantes")
    return embed
