"""
Armazenamento JSON genérico reutilizado pelos módulos de XP e economia.
Mesma filosofia do utils/config_store.py: sem dependência de banco de dados,
escrita atômica em disco, protegida por asyncio.Lock.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

CAMINHO_DADOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


class JsonStore:
    def __init__(self, nome_arquivo: str, padrao_item: dict[str, Any]):
        self.caminho = os.path.join(CAMINHO_DADOS, nome_arquivo)
        self.padrao_item = padrao_item
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

    def get(self, chave: int | str) -> dict[str, Any]:
        item = dict(self.padrao_item)
        item.update(self._dados.get(str(chave), {}))
        return item

    def top(self, n: int = 10, campo_ordenacao: str = "xp") -> list[tuple[str, dict[str, Any]]]:
        itens = [(k, {**self.padrao_item, **v}) for k, v in self._dados.items()]
        itens.sort(key=lambda kv: kv[1].get(campo_ordenacao, 0), reverse=True)
        return itens[:n]

    async def set(self, chave: int | str, **campos: Any) -> dict[str, Any]:
        async with self._lock:
            item = dict(self.padrao_item)
            item.update(self._dados.get(str(chave), {}))
            item.update(campos)
            self._dados[str(chave)] = item
            await asyncio.get_event_loop().run_in_executor(None, self._salvar_sync)
            return item

    async def incrementar(self, chave: int | str, campo: str, quantidade: int | float) -> dict[str, Any]:
        async with self._lock:
            item = dict(self.padrao_item)
            item.update(self._dados.get(str(chave), {}))
            item[campo] = item.get(campo, 0) + quantidade
            self._dados[str(chave)] = item
            await asyncio.get_event_loop().run_in_executor(None, self._salvar_sync)
            return item
