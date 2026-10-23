"""Orquestra entrada, regras e visualização sem conhecer o hardware concreto."""

import time

from .events import RESET
from .game import AcerteZeroGame, Target
from .interfaces import Display, Inputs


def run(game: AcerteZeroGame, inputs: Inputs, display: Display) -> None:
    try:
        display.show(game)
        while True:
            events = inputs.poll()
            if RESET in events:
                game.reset()
                display.show(game)
                print("Nova partida iniciada pelo juiz.")
                continue
            # Um lote com acionamentos simultâneos não ganha prioridade arbitrária.
            if len(events) == 1 and isinstance(events[0], Target):
                result = game.hit(events[0])
                if result.accepted:
                    display.show(game, result.claimed_led)
                    if result.winner is not None:
                        print(f"Jogador {result.winner} venceu! Aguardando o juiz.")
            time.sleep(0.01)
    except KeyboardInterrupt:
        pass
    finally:
        display.close()
        inputs.close()
