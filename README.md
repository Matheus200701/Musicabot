# 🎵 Musicabot Pro 2026

Bot de música profissional para Discord, reconstruído para Python 3.14+, `discord.py` 2.7.x, `yt-dlp`, FFmpeg, PyNaCl e SQLite assíncrono.

## Arquitetura

`Discord Layer → Application/Player → yt-dlp → FFmpeg → Voice`.

O projeto **não usa Lavalink, Wavelink ou Node.js como servidor de áudio**. Cada servidor possui seu próprio player e fila.

## Recursos

- `/play` com URL ou pesquisa
- `/search` com Select Menu
- `/pause`, `/resume`, `/skip`, `/stop`
- `/queue`, `/clear`, `/remove`, `/move`, `/shuffle`
- `/nowplaying`, `/volume`, `/loop`, `/replay`, `/seek`
- `/join`, `/leave`, `/autoplay`, `/stats`
- botões persistentes de player
- SQLite + aiosqlite e migração automática
- logs rotativos
- health/diagnostic
- comandos administrativos protegidos por `OWNER_ID`
- sincronização global centralizada em `setup_hook()`
- sem sincronização em `on_ready`
- Docker opcional
- CI com Python 3.14

## Requisitos

- Python 3.14.x
- FFmpeg e FFprobe no PATH
- token de aplicação Discord
- PyNaCl funcional no sistema

Python 3.14.7 é a manutenção estável usada como referência. O projeto não assume `systemd`, Docker ou root.

## Instalação

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows
# .venv\\Scripts\\activate
python -m pip install -U pip
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

No Termux, instale Python, FFmpeg e ferramentas de compilação pelo gerenciador de pacotes antes do `pip install`.

## `.env`

```env
DISCORD_TOKEN=
OWNER_ID=
BOT_PREFIX=!
DATABASE_PATH=data/bot.db
LOG_LEVEL=INFO
FFMPEG_PATH=ffmpeg
FFPROBE_PATH=ffprobe
DEFAULT_VOLUME=50
AUTO_DISCONNECT_MINUTES=5
```

Nunca versionar o `.env` real.

## Comandos administrativos

`/sync` sincroniza globalmente e `/clear_commands` remove a árvore global. Ambos exigem `OWNER_ID`.

**Importante:** comandos globais do Discord podem levar algum tempo para propagar. O bot não registra a mesma árvore em `on_ready`, Cogs e `setup_hook` ao mesmo tempo.

## Docker

```bash
docker compose up -d --build
```

O Docker é opcional. O arquivo `.env` deve existir localmente.

## Diagnóstico

`/diagnostic` verifica Discord, Gateway, FFmpeg, FFprobe, SQLite, yt-dlp, latência e uptime.

## Segurança

- nenhum token no código
- entradas de usuário não são concatenadas em shell
- limites de volume e posição são validados
- operações de yt-dlp rodam fora do event loop com `asyncio.to_thread`
- logs não devem conter credenciais

## Observação sobre fontes

A disponibilidade de plataformas externas muda com frequência. O bot usa os extractors suportados pelo yt-dlp e informa falhas de extração em vez de tentar contornar autenticação, DRM ou restrições da plataforma.

## Desenvolvimento

```bash
python -m compileall -q bot.py cogs services tests utils
pytest -q
```

A CI executa compilação e testes em Python 3.14.
