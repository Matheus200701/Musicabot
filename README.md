# FlaviMusic

Bot de música para Discord com fila, loop, shuffle, vote-skip, integração com Spotify, sistema de níveis/economia e painel web com login via Discord (OAuth2).

## Stack atual

- **Python:** 3.14.x (CI também valida 3.13)
- **Discord:** `discord.py 2.7.x`, incluindo suporte moderno de voz/DAVE/E2EE
- **Áudio:** `PyNaCl` + `davey` + FFmpeg
- **Busca/extração:** `yt-dlp` atualizado
- **Web:** FastAPI + Uvicorn
- **Deploy:** Termux, VPS Linux e Discloud

> As APIs do Discord e os provedores de áudio mudam com frequência. O projeto mantém as dependências versionadas e uma CI que testa a instalação e compilação em Python 3.13 e 3.14.

## Estrutura

```text
flavimusic/
├── bot.py
├── cogs/
│   ├── music.py
│   ├── events.py
│   ├── leveling.py
│   ├── economy.py
│   └── help.py
├── services/
│   ├── player.py
│   ├── ytdlp_service.py
│   ├── spotify_service.py
│   └── cache.py
├── utils/
│   ├── helpers.py
│   ├── logger.py
│   ├── errors.py
│   ├── permissions.py
│   ├── config_store.py
│   └── json_store.py
├── web/
├── data/
├── requirements.txt
├── .env.example
└── start.sh
```

## Criar o bot no Discord

1. Crie uma aplicação no Portal de Desenvolvedores do Discord.
2. Na aba **Bot**, gere/copiei o token e guarde-o somente no `.env` ou nas secrets do provedor.
3. Ative somente os **Privileged Gateway Intents** que o código realmente usa: `MESSAGE CONTENT` e `SERVER MEMBERS`. `VOICE STATES` é usado pelo player, mas não é um privileged intent.
4. Convide o bot com `bot` + `applications.commands` e as permissões necessárias para ver canais, enviar mensagens, conectar e falar.

## Configuração

```bash
cp .env.example .env
```

Preencha pelo menos `DISCORD_TOKEN`. Nunca publique o `.env` real.

Para o painel OAuth2, configure `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET` e `DISCORD_REDIRECT_URI` no Portal do Discord e no `.env`.

## Termux / Android

```bash
pkg update -y && pkg upgrade -y
pkg install python git ffmpeg build-essential libffi openssl libsodium -y

git clone <seu-repo> flavimusic
cd flavimusic
cp .env.example .env
python -m pip install -U pip
python -m pip install -r requirements.txt
bash start.sh
```

Para execução contínua, use `termux-wake-lock` e desative a otimização de bateria do Termux.

## VPS Linux

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg git

git clone <seu-repo> flavimusic
cd flavimusic
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
cp .env.example .env
bash start.sh
```

## Comandos

**Música:** `/tocar`, `/pular`, `/pausar`, `/continuar`, `/parar`, `/fila`, `/loop`, `/shuffle`, `/volume`, `/remover`, `/painel`.

**Configuração:** `/dj`, `/canal_musica`.

**Níveis:** `/rank`, `/leaderboard`.

**Economia:** `/saldo`, `/trabalhar`, `/transferir`, `/ranking_moedas`.

## Compatibilidade de voz

A camada de voz usa `discord.py[voice]`, `PyNaCl` e `davey`. O objetivo é acompanhar as mudanças modernas do Discord para conexões de voz e criptografia de ponta a ponta, sem depender de implementações antigas de voz.

## CI

O workflow `.github/workflows/ci.yml` instala FFmpeg/Opus, instala `requirements.txt` e executa `compileall` em Python 3.13 e 3.14 a cada push/PR na `main`.

## Segurança

- Não coloque tokens, client secrets ou cookies no Git.
- Se um token for exposto, revogue-o no Portal do Discord e gere outro.
- Para o painel público, use HTTPS e `WEB_COOKIE_HTTPS_ONLY=true`.

## Problemas comuns

- **Áudio não inicia:** confirme FFmpeg e as dependências de voz instaladas.
- **Fonte de áudio bloqueada:** atualize `yt-dlp`; provedores de vídeo podem mudar seus mecanismos sem aviso.
- **Intents:** confirme no Portal do Discord os privileged intents que o bot utiliza.
- **Painel OAuth2:** a `DISCORD_REDIRECT_URI` precisa ser exatamente igual à cadastrada no Discord.
