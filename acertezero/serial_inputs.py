"""Eventos de alvos recebidos de dois Arduino Nano pela USB serial."""

import time

from .events import RESET

from .game import Target
from .interfaces import Inputs


def parse_hit_line(line: bytes, targets_per_player: int = 5) -> Target | None:
    """Aceita apenas H,jogador,alvo,leitura; ignora mensagens de diagnóstico."""
    try:
        kind, player_text, target_text, value_text = line.decode("ascii").strip().split(",")
        player = int(player_text)
        target_number = int(target_text)
        value = int(value_text)
    except (UnicodeDecodeError, ValueError):
        return None
    if kind != "H" or player not in (1, 2):
        return None
    if not 1 <= target_number <= targets_per_player or not 0 <= value <= 1023:
        return None
    return Target(player, target_number)


class SerialTargetInputs:
    """Lê linhas completas sem bloquear o loop do jogo.

    O Arduino detecta o pulso e o envia por USB. O buffer serial preserva
    eventos produzidos enquanto a fita está atualizando a exibição.
    """

    MAX_LINE_BYTES = 64

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        targets_per_player: int = 5,
        expected_player: int | None = None,
        connection=None,
    ) -> None:
        if expected_player not in (None, 1, 2):
            raise ValueError("O jogador esperado deve ser 1 ou 2.")
        if connection is None:
            try:
                import serial
            except ImportError as exc:
                raise RuntimeError("Instale pyserial no ambiente Python da Pi: pip install pyserial") from exc
            connection = serial.Serial(port, baudrate=baudrate, timeout=0)
        self.connection = connection
        self.targets_per_player = targets_per_player
        self.expected_player = expected_player
        self._line = bytearray()
        self._discarding = False

    def poll(self) -> list[Target]:
        events = []
        available = self.connection.in_waiting
        if not available:
            return events
        for byte in self.connection.read(min(available, 4096)):
            if byte == 10:  # \n
                if not self._discarding:
                    target = parse_hit_line(bytes(self._line), self.targets_per_player)
                    if target is not None and (self.expected_player is None or target.player == self.expected_player):
                        events.append(target)
                self._line.clear()
                self._discarding = False
            elif self._discarding:
                continue
            elif len(self._line) < self.MAX_LINE_BYTES:
                self._line.append(byte)
            else:
                self._line.clear()
                self._discarding = True
        return events

    def close(self) -> None:
        self.connection.close()


class TwoPlayerInputs:
    """Agrupa eventos de duas fontes em uma pequena janela de simultaneidade."""

    def __init__(self, player_1: Inputs, player_2: Inputs,
                 judge: Inputs | None = None, window_seconds: float = 0.03,
                 clock=time.monotonic) -> None:
        if window_seconds < 0:
            raise ValueError("A janela de simultaneidade não pode ser negativa.")
        self.player_1 = player_1
        self.player_2 = player_2
        self.judge = judge
        self.window_seconds = window_seconds
        self.clock = clock
        self.pending: list[Target] = []
        self.first_at: float | None = None

    def poll(self):
        reset = self.judge is not None and RESET in self.judge.poll()
        received = self.player_1.poll() + self.player_2.poll()
        if reset:
            self.pending.clear()
            self.first_at = None
            return [RESET]
        if received:
            if self.first_at is None:
                self.first_at = self.clock()
            self.pending.extend(received)
        if self.first_at is not None and self.clock() - self.first_at >= self.window_seconds:
            batch = self.pending
            self.pending = []
            self.first_at = None
            return batch
        return []

    def close(self) -> None:
        try:
            self.player_1.close()
        finally:
            try:
                self.player_2.close()
            finally:
                if self.judge is not None:
                    self.judge.close()


# Nome anterior preservado para código que ainda importa a integração USB.
TwoNanoInputs = TwoPlayerInputs
