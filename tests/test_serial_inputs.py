import unittest
from contextlib import redirect_stdout
from io import StringIO
from types import ModuleType
from unittest.mock import patch

from acertezero.game import AcerteZeroGame, Target
from acertezero.events import RESET
from acertezero.piezo_monitor import main as monitor_main
from acertezero.piezo_game import main
from acertezero.runner import run
from acertezero.serial_inputs import SerialTargetInputs, TwoNanoInputs, parse_hit_line


class FakeSerial:
    def __init__(self):
        self.data = bytearray()
        self.closed = False

    @property
    def in_waiting(self):
        return len(self.data)

    def read(self, size):
        result = bytes(self.data[:size])
        del self.data[:size]
        return result

    def close(self):
        self.closed = True


class SerialTargetInputsTests(unittest.TestCase):
    def test_gpio_pilot_drives_targets_without_score_strip(self):
        board = ModuleType("board")
        for pin in (4, 5, 23, 24):
            setattr(board, f"D{pin}", f"gpio-{pin}")
        hardware = ModuleType("acertezero.hardware")
        mapped = {}
        opened = []

        class FakeLights:
            def __init__(self, pins):
                mapped["pins"] = pins

        class FakeDisplay:
            def __init__(self, score, lights):
                mapped["score"] = score
                mapped["lights"] = lights

        def fake_buttons(pins, debounce):
            opened.append(pins)
            return object()

        hardware.DigitalButtons = fake_buttons
        hardware.DigitalTargetLights = FakeLights
        hardware.GameDisplay = FakeDisplay
        hardware.JudgeButton = object
        hardware.ScoreStrip = lambda *args: self.fail("placar nao deve ser aberto")

        with patch.dict("sys.modules", {"board": board, "acertezero.hardware": hardware}):
            with patch("acertezero.piezo_game.sys.platform", "linux"):
                with patch("acertezero.piezo_game.run"):
                    with redirect_stdout(StringIO()):
                        main([
                            "--pilot", "--input-gpios-j1", "5", "--input-gpios-j2", "24",
                            "--target-led-pins-j1", "4", "--target-led-pins-j2", "23",
                        ])

        self.assertIsNone(mapped["score"])
        self.assertEqual(mapped["pins"], {Target(1, 1): "gpio-4", Target(2, 1): "gpio-23"})
        self.assertEqual(opened, [{Target(1, 1): "gpio-5"}, {Target(2, 1): "gpio-24"}])

    def test_gpio_cli_maps_two_base_boards_without_opening_serial(self):
        board = ModuleType("board")
        for pin in (5, 6, 7, 8, 9, 10, 11, 12, 13, 14):
            setattr(board, f"D{pin}", f"gpio-{pin}")
        hardware = ModuleType("acertezero.hardware")
        opened = []

        class FakeButtons:
            def __init__(self, pins, debounce):
                opened.append((pins, debounce))

        hardware.DigitalButtons = FakeButtons
        hardware.DigitalTargetLights = object
        hardware.GameDisplay = object
        hardware.JudgeButton = object
        hardware.ScoreStrip = object

        with patch.dict("sys.modules", {"board": board, "acertezero.hardware": hardware}):
            with patch("acertezero.piezo_game.sys.platform", "linux"):
                with patch("acertezero.piezo_game.SerialTargetInputs") as serial_inputs:
                    with patch("acertezero.piezo_game.run") as game_runner:
                        with redirect_stdout(StringIO()):
                            main([
                                "--input-gpios-j1", "5,6,7,8,9",
                                "--input-gpios-j2", "10,11,12,13,14",
                                "--input-debounce-ms", "20",
                            ])

        self.assertEqual(len(opened), 2)
        self.assertEqual(opened[0][0][Target(1, 1)], "gpio-5")
        self.assertEqual(opened[1][0][Target(2, 5)], "gpio-14")
        self.assertEqual(opened[0][1], 0.02)
        self.assertIs(game_runner.call_args.args[1].player_1.__class__, FakeButtons)
        serial_inputs.assert_not_called()

    def test_monitor_reports_both_players_and_target_five(self):
        serial_1, serial_2 = FakeSerial(), FakeSerial()
        serial_1.data.extend(b"READY\nP,1,5,0,1,2,0,50\nH,1,5,75\n")
        serial_2.data.extend(b"H,2,5,90\n")
        serials = iter((serial_1, serial_2))

        def open_input(port, expected_player):
            return SerialTargetInputs(port, expected_player=expected_player, connection=next(serials))

        output = StringIO()
        with patch("acertezero.piezo_monitor.SerialTargetInputs", side_effect=open_input):
            with patch("acertezero.piezo_monitor.time.sleep", side_effect=KeyboardInterrupt):
                with redirect_stdout(output):
                    monitor_main(["--port-j1", "J1", "--port-j2", "J2"])

        self.assertIn("Recebido: jogador 1, alvo 5", output.getvalue())
        self.assertIn("Recebido: jogador 2, alvo 5", output.getvalue())
        self.assertTrue(serial_1.closed and serial_2.closed)

    def test_pilot_cli_configures_one_target_per_player(self):
        with patch("acertezero.piezo_game.SerialTargetInputs") as serial_inputs:
            with patch("acertezero.piezo_game.run") as game_runner:
                with redirect_stdout(StringIO()):
                    main(["--port-j1", "COM3", "--port-j2", "COM4", "--pilot", "--led-count", "5"])

        self.assertEqual(game_runner.call_args.args[0].targets_per_player, 1)
        self.assertEqual(game_runner.call_args.args[0].active_targets[1], Target(1, 1))
        self.assertEqual(serial_inputs.call_count, 2)
        serial_inputs.assert_any_call("COM3", targets_per_player=1, expected_player=1)
        serial_inputs.assert_any_call("COM4", targets_per_player=1, expected_player=2)

    def test_full_cli_maps_target_lights_for_both_players(self):
        board = ModuleType("board")
        for pin in (5, 6, 12, 13, 19, 20, 21, 23, 24, 25):
            setattr(board, f"D{pin}", f"gpio-{pin}")
        board.D16 = "strip-gpio"
        hardware = ModuleType("acertezero.hardware")
        mapped = {}

        class FakeScore:
            def __init__(self, pin, count):
                mapped["score"] = (pin, count)

        class FakeLights:
            def __init__(self, pins):
                mapped["pins"] = pins

        class FakeDisplay:
            def __init__(self, score, lights):
                mapped["display"] = self

        hardware.ScoreStrip = FakeScore
        hardware.DigitalButtons = object
        hardware.DigitalTargetLights = FakeLights
        hardware.GameDisplay = FakeDisplay
        hardware.JudgeButton = object

        with patch.dict("sys.modules", {"board": board, "acertezero.hardware": hardware}):
            with patch("acertezero.piezo_game.sys.platform", "linux"):
                with patch("acertezero.piezo_game.SerialTargetInputs"):
                    with patch("acertezero.piezo_game.run") as game_runner:
                        with redirect_stdout(StringIO()):
                            main([
                                "--port-j1", "J1", "--port-j2", "J2", "--leds",
                                "--target-led-pins-j1", "5,6,12,13,19",
                                "--target-led-pins-j2", "20,21,23,24,25",
                            ])

        self.assertEqual(mapped["score"], ("strip-gpio", 31))
        self.assertEqual(mapped["pins"][Target(1, 3)], "gpio-12")
        self.assertEqual(mapped["pins"][Target(2, 5)], "gpio-25")
        self.assertEqual(len(mapped["pins"]), 10)
        self.assertIs(game_runner.call_args.args[2].display, mapped["display"])

    def test_parses_only_valid_hit_messages(self):
        self.assertEqual(parse_hit_line(b"H,1,3,254\r"), Target(1, 3))
        for line in (
            b"READY", b"bateu", b"P,1,1,0,12,1023,1,850", b"H,3,1,100",
            b"H,1,6,100", b"H,1,1,9999", b"H,1,x,100",
        ):
            with self.subTest(line=line):
                self.assertIsNone(parse_hit_line(line))

    def test_reads_partial_lines_and_bursts_without_blocking(self):
        serial = FakeSerial()
        inputs = SerialTargetInputs("ignored", connection=serial)
        serial.data.extend(b"READY\nH,1,1,2")
        self.assertEqual(inputs.poll(), [])

        serial.data.extend(b"54\r\nH,2,4,80\n")
        self.assertEqual(inputs.poll(), [Target(1, 1), Target(2, 4)])
        self.assertEqual(inputs.poll(), [])
        inputs.close()
        self.assertTrue(serial.closed)

    def test_discards_oversized_line_and_recovers_at_next_newline(self):
        serial = FakeSerial()
        inputs = SerialTargetInputs("ignored", connection=serial)
        serial.data.extend(b"x" * 100 + b"\nH,1,1,90\n")
        self.assertEqual(inputs.poll(), [Target(1, 1)])

    def test_each_port_accepts_only_its_configured_player(self):
        serial = FakeSerial()
        serial.data.extend(b"H,2,1,90\nH,1,5,100\n")
        inputs = SerialTargetInputs("ignored", expected_player=1, connection=serial)
        self.assertEqual(inputs.poll(), [Target(1, 5)])

    def test_two_ports_group_close_hits_and_reset_drops_pending(self):
        serial_1, serial_2 = FakeSerial(), FakeSerial()
        player_1 = SerialTargetInputs("j1", expected_player=1, connection=serial_1)
        player_2 = SerialTargetInputs("j2", expected_player=2, connection=serial_2)
        now = [0.0]

        class Judge:
            pressed = False
            closed = False

            def poll(self):
                if self.pressed:
                    self.pressed = False
                    return [RESET]
                return []

            def close(self):
                self.closed = True

        judge = Judge()
        inputs = TwoNanoInputs(player_1, player_2, judge, clock=lambda: now[0])
        serial_1.data.extend(b"H,1,2,90\n")
        self.assertEqual(inputs.poll(), [])
        now[0] = 0.015
        serial_2.data.extend(b"H,2,4,100\n")
        self.assertEqual(inputs.poll(), [])
        now[0] = 0.031
        self.assertEqual(inputs.poll(), [Target(1, 2), Target(2, 4)])

        serial_1.data.extend(b"H,1,1,90\n")
        self.assertEqual(inputs.poll(), [])
        judge.pressed = True
        self.assertEqual(inputs.poll(), [RESET])
        now[0] = 0.10
        self.assertEqual(inputs.poll(), [])
        inputs.close()
        self.assertTrue(serial_1.closed and serial_2.closed and judge.closed)

    def test_serial_hit_reaches_game_runner(self):
        serial = FakeSerial()
        serial.data.extend(b"H,1,1,90\n")
        inputs = SerialTargetInputs("ignored", targets_per_player=1, connection=serial)
        game = AcerteZeroGame(led_count=5, targets_per_player=1, seed=1)

        class FakeDisplay:
            def __init__(self):
                self.scores = []

            def show(self, current_game, claimed_led=None):
                self.scores.append((current_game.player_1_leds, current_game.neutral_leds))

            def close(self):
                pass

        display = FakeDisplay()
        with redirect_stdout(StringIO()), patch("acertezero.runner.time.sleep", side_effect=KeyboardInterrupt):
            run(game, inputs, display)

        self.assertEqual(display.scores, [(2, 1), (3, 0)])
        self.assertTrue(serial.closed)


if __name__ == "__main__":
    unittest.main()
