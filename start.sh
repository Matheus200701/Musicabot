#!/usr/bin/env bash
# Script de inicialização do FlaviMusic — funciona em VPS Linux e Termux (Android).
set -e

cd "$(dirname "$0")"

if [ ! -f ".env" ]; then
  echo "⚠️  Arquivo .env não encontrado. Copiando .env.example -> .env"
  cp .env.example .env
  echo "➡️  Edite o arquivo .env com seu DISCORD_TOKEN antes de continuar e rode este script novamente."
  exit 1
fi

PYTHON_BIN="python3"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "❌ python3 não encontrado. Instale o Python 3.11+ antes de continuar."
  exit 1
fi

# Cria e ativa um ambiente virtual, exceto no Termux (onde venv costuma dar problema
# com alguns pacotes nativos — nesse caso instalamos direto no ambiente do Termux).
if [ -n "$TERMUX_VERSION" ]; then
  echo "📱 Ambiente Termux detectado — instalando dependências diretamente (sem venv)."
  pip install --upgrade pip
  pip install -r requirements.txt
else
  if [ ! -d ".venv" ]; then
    echo "🐍 Criando ambiente virtual (.venv)..."
    "$PYTHON_BIN" -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
fi

echo "🚀 Iniciando o FlaviMusic..."
exec "$PYTHON_BIN" bot.py
