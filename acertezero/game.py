"""Regras do jogo, sem dependências de GPIO ou de bibliotecas de LEDs."""

from dataclasses import dataclass
from random import Random


@dataclass(frozen=True)
class Target:
    player: int
    number: int  # 1 a 5 dentro do lado do jogador


@dataclass(frozen=True)
class HitResult:
    accepted: bool
    claimed_led: int | None
    winner: int | None
    active_targets: tuple[Target, ...]


class AcerteZeroGame:
    """Um acerto ocupa um LED neutro ou toma um LED do adversário."""

    def __init__(
        self,
        led_count: int,
        targets_per_player: int = 5,
        seed: int | None = None,
    ) -> None:
        if led_count < 2:
            raise ValueError("A fita precisa ter pelo menos dois LEDs.")
        if targets_per_player < 1:
            raise ValueError("Cada jogador precisa ter pelo menos um alvo.")
        self.led_count = led_count
        self.targets_per_player = targets_per_player
        self.rng = Random(seed)
        self.player_1_leds = led_count // 2
        self.neutral_leds = led_count % 2
        self.player_2_leds = led_count // 2
        self.winner: int | None = None
        self.active_targets = {player: self._pick_target(player) for player in (1, 2)}

    def _pick_target(self, player: int, previous: Target | None = None) -> Target:
        if self.targets_per_player == 1:
            return Target(player, 1)
        choices = list(range(1, self.targets_per_player + 1))
        if previous is not None:
            choices.remove(previous.number)
        return Target(player, self.rng.choice(choices))

    def hit(self, target: Target) -> HitResult:
        """Processa um acionamento. Cada jogador tem seu próprio alvo aceso."""
        if self.winner is not None or target != self.active_targets.get(target.player):
            return HitResult(False, None, self.winner, tuple(self.active_targets.values()))

        player = target.player
        if self.neutral_leds:
            self.neutral_leds = 0
        elif player == 1:
            self.player_2_leds -= 1
        else:
            self.player_1_leds -= 1

        if player == 1:
            self.player_1_leds += 1
            claimed_led = self.player_1_leds - 1
        else:
            self.player_2_leds += 1
            claimed_led = self.player_1_leds

        if self.player_1_leds == self.led_count or self.player_2_leds == self.led_count:
            self.winner = player
            self.active_targets.clear()
        else:
            self.active_targets[player] = self._pick_target(player, previous=target)

        return HitResult(True, claimed_led, self.winner, tuple(self.active_targets.values()))

    def owner_at(self, led_index: int) -> int:
        """Retorna 1, 2 ou 0 (neutro) para um LED da fita."""
        if not 0 <= led_index < self.led_count:
            raise IndexError(led_index)
        if led_index < self.player_1_leds:
            return 1
        if led_index < self.player_1_leds + self.neutral_leds:
            return 0
        return 2
