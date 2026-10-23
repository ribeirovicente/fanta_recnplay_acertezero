"""Adaptadores opcionais da Raspberry Pi 5; as regras não importam este módulo."""

import time
from collections.abc import Mapping

import adafruit_pixelbuf
import digitalio
from adafruit_raspberry_pi5_neopixel_write import neopixel_write

from .game import Target, AcerteZeroGame


class Pi5Pixelbuf(adafruit_pixelbuf.PixelBuf):
    def __init__(self, pin, size, **kwargs):
        self._pin = pin
        super().__init__(size=size, **kwargs)

    def _transmit(self, buf):
        neopixel_write(self._pin, buf)


class ScoreStrip:
    """Exibe apenas o território de cada jogador na fita WS2812B."""

    COLORS = {0: (12, 12, 12), 1: (40, 0, 0), 2: (0, 0, 40)}

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
    """Dez botões, ativos em nível baixo e com debounce independente."""

    def __init__(self, pins: Mapping[Target, object], debounce: float = 0.05):
        self.debounce = debounce
        self.inputs = {}
        self.stable = {}
        self.last_raw = {}
        self.changed_at = {}
        now = time.monotonic()
        for target, pin in pins.items():
            port = digitalio.DigitalInOut(pin)
            port.direction = digitalio.Direction.INPUT
            port.pull = digitalio.Pull.UP
            pressed = not port.value
            self.inputs[target] = port
            self.stable[target] = pressed
            self.last_raw[target] = pressed
            self.changed_at[target] = now

    def poll(self) -> list[Target]:
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
        for port in self.inputs.values():
            port.deinit()


class DigitalTargetLights:
    """Uma saída digital por LED indicador, através de resistor/driver adequado."""

    def __init__(self, pins: Mapping[Target, object]):
        self.outputs = {}
        for target, pin in pins.items():
            port = digitalio.DigitalInOut(pin)
            port.direction = digitalio.Direction.OUTPUT
            port.value = False
            self.outputs[target] = port

    def show(self, active: tuple[Target, ...]) -> None:
        # Apaga antes de acender: apenas os alvos escolhidos ficam iluminados.
        for port in self.outputs.values():
            port.value = False
        for target in active:
            self.outputs[target].value = True

    def close(self) -> None:
        self.show(())
        for port in self.outputs.values():
            port.deinit()


class GameDisplay:
    def __init__(self, score: ScoreStrip, targets: DigitalTargetLights):
        self.score = score
        self.targets = targets

    def show(self, game: AcerteZeroGame, claimed_led: int | None = None) -> None:
        self.targets.show(tuple(game.active_targets.values()))
        self.score.show(game, claimed_led)

    def close(self) -> None:
        self.targets.close()
        self.score.close()
