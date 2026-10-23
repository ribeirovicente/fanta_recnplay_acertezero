"""Sequência de iluminação dos alvos, independente dos pinos físicos."""

import time
from collections.abc import Callable
from typing import Protocol

from .game import Target


class TargetLights(Protocol):
    def show(self, active: tuple[Target, ...]) -> None: ...


def play_start_animation(
    lights: TargetLights,
    targets_per_player: int,
    active: tuple[Target, ...],
    frame_seconds: float = 0.08,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Percorre os dois lados em conjunto e termina nos alvos sorteados."""
    if targets_per_player < 1:
        raise ValueError("Cada jogador precisa ter pelo menos um alvo.")
    if frame_seconds < 0:
        raise ValueError("A duração de cada quadro não pode ser negativa.")

    sequence = list(range(1, targets_per_player + 1))
    sequence.extend(range(targets_per_player - 1, 0, -1))
    for number in sequence:
        lights.show((Target(1, number), Target(2, number)))
        sleep(frame_seconds)
    lights.show(())
    sleep(frame_seconds)
    lights.show(active)
