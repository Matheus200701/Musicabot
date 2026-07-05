"""
Cache em memória com expiração (TTL) para resultados de busca do yt-dlp.

Evita re-extrair a mesma música/URL repetidamente (o que é lento e pode levar
a bloqueios temporários do YouTube), sem depender de Redis ou outro serviço
externo — mantendo o projeto leve para rodar em Termux/VPS pequena.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any


class TTLCache:
    def __init__(self, ttl_segundos: int = 1800, tamanho_maximo: int = 300):
        self.ttl = ttl_segundos
        self.tamanho_maximo = tamanho_maximo
        self._dados: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def get(self, chave: str) -> Any | None:
        item = self._dados.get(chave)
        if not item:
            return None
        expira_em, valor = item
        if time.monotonic() > expira_em:
            self._dados.pop(chave, None)
            return None
        # LRU: move para o fim ao acessar
        self._dados.move_to_end(chave)
        return valor

    def set(self, chave: str, valor: Any) -> None:
        self._dados[chave] = (time.monotonic() + self.ttl, valor)
        self._dados.move_to_end(chave)
        while len(self._dados) > self.tamanho_maximo:
            self._dados.popitem(last=False)

    def limpar_expirados(self) -> int:
        agora = time.monotonic()
        chaves_expiradas = [k for k, (exp, _) in self._dados.items() if agora > exp]
        for k in chaves_expiradas:
            self._dados.pop(k, None)
        return len(chaves_expiradas)

    def __len__(self) -> int:
        return len(self._dados)


# Cache compartilhado para buscas do yt-dlp (título, thumbnail, duração, url de stream)
cache_busca = TTLCache(ttl_segundos=1800, tamanho_maximo=500)
