"""Garante que uma falha de GPIO não deixe reservas parciais no processo."""

import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from acertezero.game import Target


class HardwareCleanupTests(unittest.TestCase):
    def test_partial_gpio_claim_releases_first_pin(self):
        digitalio = ModuleType("digitalio")
        digitalio.Direction = type("Direction", (), {"INPUT": 0, "OUTPUT": 1})
        digitalio.Pull = type("Pull", (), {"UP": 1})
        opened = []

        class FakePort:
            def __init__(self, pin):
                if len(opened) == 1:
                    raise OSError("GPIO busy")
                self.pin = pin
                self.value = True
                self.closed = False
                opened.append(self)

            def deinit(self):
                self.closed = True

        digitalio.DigitalInOut = FakePort
        pixelbuf = ModuleType("adafruit_pixelbuf")
        pixelbuf.PixelBuf = object
        neopixel = ModuleType("adafruit_raspberry_pi5_neopixel_write")
        neopixel.neopixel_write = lambda *args: None
        path = Path(__file__).parents[1] / "acertezero" / "hardware.py"
        spec = importlib.util.spec_from_file_location("acertezero._hardware_cleanup_test", path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"digitalio": digitalio, "adafruit_pixelbuf": pixelbuf,
                                      "adafruit_raspberry_pi5_neopixel_write": neopixel}):
            spec.loader.exec_module(module)

        pins = {Target(1, 1): "first", Target(1, 2): "busy"}
        with self.assertRaisesRegex(OSError, "GPIO busy"):
            module.DigitalButtons(pins)
        self.assertTrue(opened[0].closed)

        opened.clear()
        with self.assertRaisesRegex(OSError, "GPIO busy"):
            module.DigitalTargetLights(pins)
        self.assertTrue(opened[0].closed)


if __name__ == "__main__":
    unittest.main()
