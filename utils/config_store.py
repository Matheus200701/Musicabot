"""
Armazenamento simples de configuração por servidor (guild), em JSON.

Não usa banco de dados para manter o projeto leve o bastante para rodar em
Termux/Android. Guarda coisas como: canal de música exclusivo, prefixo custom,
cargo de DJ, e é usado tanto pelo bot quanto pelo painel web (mesmo processo).

Todas as operações são protegidas por um asyncio.Lock e a escrita em disco é
feita de forma atômica (arquivo temporário + rename) para evitar corrupção
caso o processo seja encerrado no meio de uma escrita.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

CAMINHO_DADOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ARQUIVO_CONFIG = os.path.join(CAMINHO_DADOS, "guild_configs.json")

_PADRAO_GUILD = {
    "prefixo": None,          # None = usa o prefixo global do .env
    "canal_musica_id": None,  # None = comandos de música liberados em qualquer canal
    "dj_role_id": None,       # None = qualquer um pode usar comandos de DJ (skip forçado etc.)
    "volume": 0.5,
}


class ConfigStore:
    def __init__(self, caminho: str = ARQUIVO_CONFIG):
        self.caminho = caminho
        self._lock = asyncio.Lock()
        self._dados: dict[str, dict[str, Any]] = {}
        self._carregar()

    def _carregar(self) -> None:
        os.makedirs(CAMINHO_DADOS, exist_ok=True)
        if os.path.exists(self.caminho):
            try:
                with open(self.caminho, "r", encoding="utf-8") as f:
                    self._dados = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._dados = {}
        else:
            self._dados = {}

    def _salvar_sync(self) -> None:
        os.makedirs(CAMINHO_DADOS, exist_ok=True)
        tmp = f"{self.caminho}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._dados, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.caminho)

    def get(self, guild_id: int) -> dict[str, Any]:
        cfg = dict(_PADRAO_GUILD)
        cfg.update(self._dados.get(str(guild_id), {}))
        return cfg

    async def set(self, guild_id: int, **campos: Any) -> dict[str, Any]:
        async with self._lock:
            atual = dict(_PADRAO_GUILD)
            atual.update(self._dados.get(str(guild_id), {}))
            atual.update({k: v for k, v in campos.items() if v is not None or k in campos})
            self._dados[str(guild_id)] = atual
            await asyncio.get_event_loop().run_in_executor(None, self._salvar_sync)
            return atual


# Instância única compartilhada pelo bot e pelo painel web
config_store = ConfigStore()
