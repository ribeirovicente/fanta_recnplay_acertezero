"""Adaptadores opcionais da Raspberry Pi 5; as regras não importam este módulo."""

import time
from collections.abc import Mapping
from contextlib import suppress

import adafruit_pixelbuf
import digitalio
from adafruit_raspberry_pi5_neopixel_write import neopixel_write

from .events import RESET, ResetEvent
from .game import Target, AcerteZeroGame
from .target_lights import play_start_animation


class Pi5Pixelbuf(adafruit_pixelbuf.PixelBuf):
    def __init__(self, pin, size, **kwargs):
        self._pin = pin
        super().__init__(size=size, **kwargs)

    def _transmit(self, buf):
        neopixel_write(self._pin, buf)


class ScoreStrip:
    """Exibe apenas o território de cada jogador na fita WS2812B."""

    COLORS = {0: (12, 12, 12), 1: (1, 48, 13), 2: (15, 12, 0)}

    def __init__(self, data_pin, led_count: int):
        self.pixels = Pi5Pixelbuf(data_pin, led_count, auto_write=False, byteorder="BGR")

    def show(self, game: AcerteZeroGame, claimed_led: int | None = None) -> None:
        if claimed_led is not None:
            self.pixels[claimed_led] = (80, 80, 80)
            self.pixels.show()
            time.sleep(0.12)
        for index in range(game.led_count):
            self.pixels[index] = self.COLORS[game.owner_at(index)]
        self.pixels.show()

    def close(self) -> None:
        pass


class DigitalButtons:
    """Entradas de toque ativas em nível baixo, com debounce independente.

    Aceita tanto botões quanto ResIn das Bases, que têm pull-up externo de 10 kΩ.
    """

    def __init__(self, pins: Mapping[Target, object], debounce: float = 0.05):
        self.debounce = debounce
        self.inputs = {}
        self.stable = {}
        self.last_raw = {}
        self.changed_at = {}
        now = time.monotonic()
        try:
            for target, pin in pins.items():
                port = digitalio.DigitalInOut(pin)
                self.inputs[target] = port
                port.direction = digitalio.Direction.INPUT
                port.pull = digitalio.Pull.UP
                pressed = not port.value
                self.stable[target] = pressed
                self.last_raw[target] = pressed
                self.changed_at[target] = now
        except BaseException:
            with suppress(Exception):
                self.close()
            raise

    def poll(self) -> list[Target | ResetEvent]:
        now = time.monotonic()
        events = []
        for target, port in self.inputs.items():
            pressed = not port.value
            if pressed != self.last_raw[target]:
                self.last_raw[target] = pressed
                self.changed_at[target] = now
            if pressed != self.stable[target] and now - self.changed_at[target] >= self.debounce:
                self.stable[target] = pressed
                if pressed:
                    events.append(target)
        return events

    def close(self) -> None:
        error = None
        for port in self.inputs.values():
            try:
                port.deinit()
            except Exception as exc:
                if error is None:
                    error = exc
        if error is not None:
            raise error


class JudgeButton:
    """Botão do juiz entre um GPIO e GND, com pull-up e debounce."""

    def __init__(self, pin, debounce: float = 0.05):
        self.port = digitalio.DigitalInOut(pin)
        try:
            self.port.direction = digitalio.Direction.INPUT
            self.port.pull = digitalio.Pull.UP
            self.debounce = debounce
            self.stable = not self.port.value
            self.last_raw = self.stable
            self.changed_at = time.monotonic()
        except BaseException:
            with suppress(Exception):
                self.port.deinit()
            raise

    def poll(self) -> list[Target | ResetEvent]:
        now = time.monotonic()
        pressed = not self.port.value
        if pressed != self.last_raw:
            self.last_raw = pressed
            self.changed_at = now
        if pressed != self.stable and now - self.changed_at >= self.debounce:
            self.stable = pressed
            if pressed:
                return [RESET]
        return []

    def close(self) -> None:
        self.port.deinit()


class DigitalTargetLights:
    """Uma saída ativa em nível alto por alvo.

    Na Base, cada saída ResOut aciona um opto que informa o Nano do alvo ativo.
    """

    def __init__(self, pins: Mapping[Target, object]):
        self.outputs = {}
        try:
            for target, pin in pins.items():
                port = digitalio.DigitalInOut(pin)
                self.outputs[target] = port
                port.direction = digitalio.Direction.OUTPUT
                port.value = False
        except BaseException:
            with suppress(Exception):
                self.close()
            raise

    def show(self, active: tuple[Target, ...]) -> None:
        # Apaga antes de acender: apenas os alvos escolhidos ficam iluminados.
        for port in self.outputs.values():
            port.value = False
        for target in active:
            port = self.outputs.get(target)
            if port is not None:
                port.value = True

    def close(self) -> None:
        error = None
        for port in self.outputs.values():
            with suppress(Exception):
                port.value = False
            try:
                port.deinit()
            except Exception as exc:
                if error is None:
                    error = exc
        if error is not None:
            raise error


class GameDisplay:
    def __init__(self, score: ScoreStrip | None, targets: DigitalTargetLights):
        self.score = score
        self.targets = targets

    def show(self, game: AcerteZeroGame, claimed_led: int | None = None) -> None:
        if game.targets_per_player == 1 and game.active_targets:
            # No piloto o mesmo Nano continua sorteado; ele precisa ver A0 alto
            # antes de aceitar outro acerto na proxima ativacao.
            self.targets.show(())
            time.sleep(0.03)
        self.targets.show(tuple(game.active_targets.values()))
        if self.score is not None:
            self.score.show(game, claimed_led)

    def start(self, game: AcerteZeroGame) -> None:
        """Anima os indicadores no início ou reinício e revela os alvos ativos."""
        if self.score is not None:
            self.score.show(game)
        play_start_animation(
            self.targets,
            game.targets_per_player,
            tuple(game.active_targets.values()),
        )

    def close(self) -> None:
        try:
            self.targets.close()
        finally:
            if self.score is not None:
                self.score.close()
