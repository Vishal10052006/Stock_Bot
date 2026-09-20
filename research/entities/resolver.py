"""RB-3 deterministic symbol/entity resolution."""
from __future__ import annotations


class EntityResolver:
    def __init__(self, aliases: dict[str, str] | None = None) -> None:
        self._aliases = {k.upper(): v.upper() for k, v in (aliases or {}).items()}

    def resolve(self, text: str) -> tuple[str, ...]:
        tokens = {token.strip(".,:;()[]{}") for token in text.upper().split()}
        return tuple(sorted({self._aliases[t] for t in tokens if t in self._aliases}))
