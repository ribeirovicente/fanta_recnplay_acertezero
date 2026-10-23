"""Contratos que isolam as regras de entrada e iluminação."""

from typing import Protocol

from .game import Target, AcerteZeroGame


class Inputs(Protocol):
    def poll(self) -> list[Target]:
        """Devolve somente novos acionamentos, com debounce quando necessário."""

    def close(self) -> None: ...


class Display(Protocol):
    def show(self, game: AcerteZeroGame, claimed_led: int | None = None) -> None:
        """Exibe placar e os dois alvos ativos durante a partida."""

    def close(self) -> None: ...
