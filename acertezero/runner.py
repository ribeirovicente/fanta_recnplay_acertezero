"""Orquestra entrada, regras e visualização sem conhecer o hardware concreto."""

import time

from .game import AcerteZeroGame
from .interfaces import Display, Inputs


def run(game: AcerteZeroGame, inputs: Inputs, display: Display) -> None:
    try:
        display.show(game)
        while game.winner is None:
            events = inputs.poll()
            # Um lote com acionamentos simultâneos não ganha prioridade arbitrária.
            if len(events) == 1:
                result = game.hit(events[0])
                if result.accepted:
                    display.show(game, result.claimed_led)
            time.sleep(0.01)
        print(f"Jogador {game.winner} venceu!")
    finally:
        display.close()
        inputs.close()
