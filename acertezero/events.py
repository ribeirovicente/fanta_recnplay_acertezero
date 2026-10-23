"""Eventos de controle independentes dos alvos dos jogadores."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResetEvent:
    """Pedido do juiz para iniciar uma nova partida."""


RESET = ResetEvent()
