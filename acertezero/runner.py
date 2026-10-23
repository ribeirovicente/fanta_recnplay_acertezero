"""Orquestra entrada, regras e visualização sem conhecer o hardware concreto."""

import time

from .events import RESET
from .game import AcerteZeroGame, Target
from .interfaces import Display, Inputs, show_start


def run(game: AcerteZeroGame, inputs: Inputs, display: Display) -> None:
    try:
        show_start(display, game)
        while True:
            events = inputs.poll()
            if RESET in events:
                game.reset()
                show_start(display, game)
                print("Nova partida iniciada pelo juiz.")
                continue
            targets = [event for event in events if isinstance(event, Target)]
            if targets:
                result = game.hit_many(targets)
                if result.accepted_targets:
                    display.show(game, result.claimed_led)
                    if result.winner is not None:
                        print(f"Jogador {result.winner} venceu! Aguardando o juiz.")
            time.sleep(0.01)
    except KeyboardInterrupt:
        pass
    finally:
        display.close()
        inputs.close()
