# FlaviMusic

Bot de música para Discord com fila, loop, shuffle, vote-skip, integração com
Spotify, sistema de níveis/economia e um painel web completo com login via
Discord (OAuth2) para controlar a música pelo navegador.

Construído em cima do projeto original, mantendo `discord.py==2.4.0` (versão
recomendada para ARM/Termux) e `yt-dlp`.

---

## Estrutura do projeto

```
flavimusic/
├── bot.py                  # ponto de entrada — roda o bot e o painel web juntos
├── cogs/
│   ├── music.py            # comandos slash de música + botões
│   ├── events.py           # on_ready, erros globais, reconexão automática
│   ├── leveling.py         # sistema de XP/níveis
│   ├── economy.py          # economia simples (moedas)
│   └── help.py             # /ajuda interativo
├── services/
│   ├── player.py           # núcleo do player: fila, loop, shuffle, vote-skip
│   ├── ytdlp_service.py    # wrapper do yt-dlp com cache
│   ├── spotify_service.py  # conversão de links do Spotify -> busca no YouTube
│   └── cache.py            # cache TTL em memória
├── utils/
│   ├── helpers.py          # embeds, formatação de duração/progresso
│   ├── logger.py           # logs em console + arquivo (logs/flavimusic.log)
│   ├── errors.py           # exceções customizadas + handler global
│   ├── permissions.py      # regras de DJ/vote-skip
│   ├── config_store.py     # config por servidor (canal, DJ role) em JSON
│   └── json_store.py       # base de armazenamento usada por XP/economia
├── web/                    # painel FastAPI (login Discord, dashboard, API)
├── data/                   # arquivos JSON gerados em runtime (git-ignored)
├── requirements.txt
├── .env.example
├── start.sh                # inicia o bot (VPS ou Termux)
└── discloud.config         # deploy na Discloud
```

---

## 1. Criar o bot no Discord

1. Acesse https://discord.com/developers/applications e crie uma aplicação.
2. Na aba **Bot**, clique em "Reset Token" e copie o token (você vai colar no `.env`).
3. Ainda na aba **Bot**, em "Privileged Gateway Intents", ative:
   - **MESSAGE CONTENT INTENT**
   - **SERVER MEMBERS INTENT**
4. Convide o bot para seu servidor com os escopos `bot` e `applications.commands`
   e permissões: Ver canais, Enviar mensagens, Conectar, Falar, Usar atividades de voz.

### Habilitar o painel web (OAuth2) — opcional, mas recomendado

1. Na mesma aplicação, vá em **OAuth2 → General**.
2. Copie o **Client ID** e o **Client Secret** para o `.env` (`DISCORD_CLIENT_ID` / `DISCORD_CLIENT_SECRET`).
3. Em **Redirects**, adicione a URL exata que você vai usar, por exemplo:
   - Local/Termux: `http://localhost:8000/auth/callback`
   - VPS com domínio: `https://seu-dominio.com/auth/callback`
4. Coloque essa mesma URL em `DISCORD_REDIRECT_URI` no `.env`.

### Habilitar Spotify — opcional

1. Crie um app gratuito em https://developer.spotify.com/dashboard.
2. Copie o **Client ID** e **Client Secret** para `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` no `.env`.
3. Sem isso, links do Spotify simplesmente não vão funcionar (o resto do bot funciona normalmente).

---

## 2. Configurar o `.env`

```bash
cp .env.example .env
```

Edite o `.env` e preencha pelo menos `DISCORD_TOKEN`. Gere uma chave de sessão para o painel:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Cole o resultado em `WEB_SESSION_SECRET`.

> ⚠️ **Nunca** suba o `.env` real (com valores preenchidos) para o GitHub, Discloud
> ou qualquer lugar público. Só o `.env.example` deve ser versionado.
> Se algum token/segredo já foi exposto acidentalmente, revogue e gere um novo
> imediatamente no Portal de Desenvolvedores do Discord.

---

## 3. Rodar — Termux (Android)

Testado num Samsung A10s (2–3 GB de RAM) — feche apps pesados antes de instalar.

```bash
pkg update -y && pkg upgrade -y
pkg install python git ffmpeg build-essential libffi openssl libsodium -y

cd ~
git clone <seu-repo> flavimusic   # ou extraia o zip aqui
cd flavimusic

cp .env.example .env
nano .env   # preencha DISCORD_TOKEN (e o resto, se quiser o painel/Spotify)

bash start.sh
```

Para manter rodando em segundo plano:

```bash
pkg install termux-wake-lock -y   # evita a CPU suspender
termux-wake-lock
nohup bash start.sh > flavimusic.log 2>&1 &
```

Desative também a otimização de bateria do Termux em
`Ajustes > Apps > Termux > Bateria > Sem restrições`.

Para acessar o painel web de fora da rede local, use um túnel:

```bash
pkg install cloudflared -y
cloudflared tunnel --url http://localhost:8000
```

Se usar um túnel público, é essencial já ter configurado `DISCORD_REDIRECT_URI`
com a URL pública do túnel (e cadastrado essa mesma URL nos Redirects do Discord).

---

## 4. Rodar — VPS Linux

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip ffmpeg git

git clone <seu-repo> flavimusic
cd flavimusic
cp .env.example .env
nano .env

bash start.sh
```

Para manter rodando permanentemente, use um `systemd` service ou `tmux`/`screen`:

```bash
sudo tee /etc/systemd/system/flavimusic.service > /dev/null <<'EOF'
[Unit]
Description=FlaviMusic
After=network.target

[Service]
WorkingDirectory=/caminho/para/flavimusic
ExecStart=/caminho/para/flavimusic/.venv/bin/python bot.py
Restart=on-failure
EnvironmentFile=/caminho/para/flavimusic/.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now flavimusic
```

Se for expor o painel web publicamente, coloque um proxy reverso (nginx/Caddy)
na frente com HTTPS, e defina `WEB_COOKIE_HTTPS_ONLY=true` no `.env`.

---

## 5. Rodar — Discloud

1. Zipe a pasta do projeto **sem** o `.env` real (o `discloud.config` já vem incluso).
2. Suba o zip no painel da Discloud ou pelo bot oficial da Discloud no Discord.
3. Na aba **Variáveis** do app criado, cole todas as variáveis do `.env.example`
   com os valores reais (o `DISCORD_TOKEN` nunca deve ir dentro do zip).
4. Ajuste `RAM` no `discloud.config` se necessário (512 MB é um bom ponto de partida).

Documentação oficial: https://docs.discloud.app/

---

## Comandos

Veja a lista completa a qualquer momento com `/ajuda` (menu interativo). Resumo:

**Música**
`/tocar` `/pular` `/pausar` `/continuar` `/parar` `/fila` `/loop` `/shuffle`
`/volume` `/remover` `/painel`

**Configuração** (requer permissão de Gerenciar Servidor)
`/dj` `/canal_musica`

**Níveis** — `/rank` `/leaderboard`
**Economia** — `/saldo` `/trabalhar` `/transferir` `/ranking_moedas`

### Regras de vote-skip

- Se você é a única pessoa humana no canal de voz, tem o cargo de DJ, ou tem
  permissão de Gerenciar Canais/Servidor: `/pular` funciona instantaneamente.
- Caso contrário, `/pular` registra um voto; quando mais da metade das pessoas
  no canal votarem, a música é pulada.
- Pelo painel web, quem acessa já tem permissão de Gerenciar Servidor — então
  pular pelo painel é sempre instantâneo.

---

## Painel web

Depois de rodar o bot, acesse `http://localhost:8000` (ou o host configurado).
Faça login com Discord, escolha um servidor onde você tenha permissão de
Gerenciar Servidor, e controle a música em tempo real (WebSocket), veja a fila,
e configure canal de música / cargo de DJ.

Desative com `WEB_PANEL_ATIVO=false` no `.env` caso não queira usar.

---

## Problemas comuns

- **Erro de compilação ao instalar discord.py/PyNaCl**: confirme que instalou
  `build-essential`, `libffi` e `libsodium` antes.
- **yt-dlp dizendo que precisa fazer login / vídeo bloqueado**: rode
  `pip install -U yt-dlp` — o YouTube muda suas proteções com frequência e o
  yt-dlp é atualizado constantemente para acompanhar.
- **Bot cai quando a tela do celular apaga (Termux)**: veja a seção 3 (wake-lock
  + otimização de bateria desativada).
- **Login do painel falha com "state inválido"**: normalmente é cookie de sessão
  expirado — tente logar novamente. Confirme também que `DISCORD_REDIRECT_URI`
  no `.env` é *exatamente* igual à URL cadastrada em "Redirects" no Discord.
- **Links do Spotify não funcionam**: confirme que `SPOTIFY_CLIENT_ID` e
  `SPOTIFY_CLIENT_SECRET` estão preenchidos no `.env`.
# Musicabot
