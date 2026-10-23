"""Contratos que isolam as regras de entrada e iluminação."""

from typing import Protocol

from .events import ResetEvent
from .game import Target, AcerteZeroGame


class Inputs(Protocol):
    def poll(self) -> list[Target | ResetEvent]:
        """Devolve somente novos acionamentos, com debounce quando necessário."""

    def close(self) -> None: ...


class MergedInputs:
    """Reúne fontes de entrada, como alvos e botão do juiz."""

    def __init__(self, *sources: Inputs):
        self.sources = sources

    def poll(self) -> list[Target | ResetEvent]:
        events = []
        for source in self.sources:
            events.extend(source.poll())
        return events

    def close(self) -> None:
        for source in self.sources:
            source.close()


class Display(Protocol):
    def show(self, game: AcerteZeroGame, claimed_led: int | None = None) -> None:
        """Exibe placar e os dois alvos ativos durante a partida."""

    def close(self) -> None: ...


def show_start(display: Display, game: AcerteZeroGame) -> None:
    """Usa a animação opcional do display, preservando displays simples."""
    start = getattr(display, "start", None)
    if start is None:
        display.show(game)
    else:
        start(game)
