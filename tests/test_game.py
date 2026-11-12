import importlib
import unittest
from types import ModuleType
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from acertezero.events import RESET
from acertezero.game import Target, AcerteZeroGame
from acertezero.runner import run
from acertezero.simulator import main, parse_target_led_pins, run_simulation
from acertezero.target_lights import play_start_animation


class AcerteZeroGameTests(unittest.TestCase):
    def test_starts_with_one_target_for_each_player(self):
        game = AcerteZeroGame(led_count=6, seed=1)
        self.assertEqual(set(game.active_targets), {1, 2})
        self.assertEqual(game.active_targets[1].player, 1)
        self.assertEqual(game.active_targets[2].player, 2)

    def test_odd_strip_claims_center_then_opponent_led(self):
        game = AcerteZeroGame(led_count=5, seed=1)
        self.assertEqual([game.owner_at(i) for i in range(5)], [1, 1, 0, 2, 2])

        first = game.hit(game.active_targets[1])
        self.assertEqual(first.claimed_led, 2)
        self.assertEqual([game.owner_at(i) for i in range(5)], [1, 1, 1, 2, 2])

        second = game.hit(game.active_targets[2])
        self.assertEqual(second.claimed_led, 2)
        self.assertEqual([game.owner_at(i) for i in range(5)], [1, 1, 2, 2, 2])

    def test_inactive_target_is_ignored(self):
        game = AcerteZeroGame(led_count=4, seed=1)
        before = (game.player_1_leds, game.player_2_leds, game.active_targets.copy())
        inactive_number = 1 if game.active_targets[2].number != 1 else 2
        result = game.hit(Target(2, inactive_number))
        self.assertFalse(result.accepted)
        self.assertEqual(before, (game.player_1_leds, game.player_2_leds, game.active_targets))

    def test_hit_refreshes_only_scoring_players_target(self):
        game = AcerteZeroGame(led_count=6, seed=1)
        old_j1 = game.active_targets[1]
        old_j2 = game.active_targets[2]

        game.hit(old_j1)

        self.assertNotEqual(game.active_targets[1], old_j1)
        self.assertEqual(game.active_targets[2], old_j2)
        self.assertFalse(game.hit(old_j1).accepted)
        self.assertTrue(game.hit(old_j2).accepted)

    def test_win_freezes_score_and_turns_off_target(self):
        game = AcerteZeroGame(led_count=2, seed=1)
        result = game.hit(game.active_targets[1])
        self.assertEqual(result.winner, 1)
        self.assertEqual(game.active_targets, {})
        self.assertFalse(game.hit(Target(2, 1)).accepted)
        self.assertEqual((game.player_1_leds, game.player_2_leds), (2, 0))

    def test_reset_after_win_starts_new_match(self):
        game = AcerteZeroGame(led_count=3, seed=1)
        game.hit(game.active_targets[1])
        game.hit(game.active_targets[1])
        self.assertEqual(game.winner, 1)

        game.reset()

        self.assertIsNone(game.winner)
        self.assertEqual((game.player_1_leds, game.neutral_leds, game.player_2_leds), (1, 1, 1))
        self.assertEqual(game.hits_by_player, {1: 0, 2: 0})
        self.assertEqual(set(game.active_targets), {1, 2})
        self.assertTrue(game.hit(game.active_targets[2]).accepted)

    def test_simultaneous_hits_cancel_score_and_refresh_both_targets(self):
        for led_count in (5, 6):
            with self.subTest(led_count=led_count):
                game = AcerteZeroGame(led_count=led_count, seed=1)
                old = game.active_targets.copy()
                owners = tuple(game.owner_at(i) for i in range(led_count))

                result = game.hit_many([old[2], old[1]])

                self.assertEqual(result.accepted_targets, (old[1], old[2]))
                self.assertIsNone(result.claimed_led)
                self.assertEqual(tuple(game.owner_at(i) for i in range(led_count)), owners)
                self.assertEqual(game.hits_by_player, {1: 1, 2: 1})
                self.assertNotEqual(game.active_targets[1], old[1])
                self.assertNotEqual(game.active_targets[2], old[2])
                self.assertIsNone(game.winner)

    def test_batch_validates_once_and_ignores_duplicates_and_inactive_targets(self):
        game = AcerteZeroGame(led_count=5, seed=1)
        active = game.active_targets[1]
        inactive_number = 1 if game.active_targets[2].number != 1 else 2

        result = game.hit_many([Target(2, inactive_number), active, active])

        self.assertEqual(result.accepted_targets, (active,))
        self.assertEqual(game.hits_by_player, {1: 1, 2: 0})
        self.assertEqual((game.player_1_leds, game.neutral_leds, game.player_2_leds), (3, 0, 2))

    def test_simultaneous_hit_cannot_end_match_by_polling_order(self):
        game = AcerteZeroGame(led_count=2, seed=1)
        result = game.hit_many(list(game.active_targets.values()))
        self.assertIsNone(result.winner)
        self.assertEqual((game.player_1_leds, game.player_2_leds), (1, 1))
        self.assertEqual(set(game.active_targets), {1, 2})


class TargetAnimationTests(unittest.TestCase):
    def test_score_flashes_five_times_before_staying_on(self):
        pixelbuf = ModuleType("adafruit_pixelbuf")
        pixelbuf.PixelBuf = type("PixelBuf", (), {})
        neopixel_write = ModuleType("adafruit_raspberry_pi5_neopixel_write")
        neopixel_write.neopixel_write = lambda *args: None
        digitalio = ModuleType("digitalio")
        delays = []

        class FakePixels:
            def __init__(self, pin, count, **kwargs):
                self.values = [None] * count
                self.frames = []

            def __len__(self):
                return len(self.values)

            def __setitem__(self, index, value):
                self.values[index] = value

            def show(self):
                self.frames.append(tuple(self.values))

        dependencies = {
            "adafruit_pixelbuf": pixelbuf,
            "adafruit_raspberry_pi5_neopixel_write": neopixel_write,
            "digitalio": digitalio,
        }
        with patch.dict("sys.modules", dependencies):
            hardware = importlib.import_module("acertezero.hardware")
            with patch.object(hardware, "Pi5Pixelbuf", FakePixels), \
                    patch.object(hardware.time, "sleep", side_effect=delays.append):
                game = AcerteZeroGame(led_count=5, seed=1)
                score = hardware.ScoreStrip("data", 5)
                score.start(game)

        off = ((0, 0, 0),) * game.led_count
        on = tuple(hardware.ScoreStrip.COLORS[game.owner_at(i)] for i in range(game.led_count))
        self.assertEqual(score.pixels.frames, [off] + [frame for _ in range(5) for frame in (on, off)] + [on])
        self.assertEqual(delays, [0.12] * 10)

        score.close()
        self.assertEqual(score.pixels.frames[-1], off)

    def test_start_keeps_targets_off_until_score_flashes_finish(self):
        pixelbuf = ModuleType("adafruit_pixelbuf")
        pixelbuf.PixelBuf = type("PixelBuf", (), {})
        neopixel_write = ModuleType("adafruit_raspberry_pi5_neopixel_write")
        neopixel_write.neopixel_write = lambda *args: None
        digitalio = ModuleType("digitalio")
        events = []

        class FakeScore:
            def start(self, game):
                events.append("score flashes")

        class FakeLights:
            def show(self, active):
                events.append(("targets", active))

        dependencies = {
            "adafruit_pixelbuf": pixelbuf,
            "adafruit_raspberry_pi5_neopixel_write": neopixel_write,
            "digitalio": digitalio,
        }
        with patch.dict("sys.modules", dependencies):
            hardware = importlib.import_module("acertezero.hardware")
            with patch.object(hardware, "play_start_animation", side_effect=lambda *args: events.append("target sweep")):
                display = hardware.GameDisplay(FakeScore(), FakeLights())
                game = AcerteZeroGame(led_count=5, seed=1)
                display.start(game)
                game.reset()
                display.start(game)

        expected = [("targets", ()), "score flashes", "target sweep"]
        self.assertEqual(events, expected * 2)

    def test_score_pulse_uses_scoring_players_color(self):
        pixelbuf = ModuleType("adafruit_pixelbuf")
        pixelbuf.PixelBuf = type("PixelBuf", (), {})
        neopixel_write = ModuleType("adafruit_raspberry_pi5_neopixel_write")
        neopixel_write.neopixel_write = lambda *args: None
        digitalio = ModuleType("digitalio")

        class FakePixels:
            def __init__(self, pin, count, **kwargs):
                self.values = [None] * count
                self.frames = []
                self.byteorder = kwargs["byteorder"]

            def __setitem__(self, index, value):
                self.values[index] = value

            def show(self):
                self.frames.append(self.values.copy())

        dependencies = {
            "adafruit_pixelbuf": pixelbuf,
            "adafruit_raspberry_pi5_neopixel_write": neopixel_write,
            "digitalio": digitalio,
        }
        with patch.dict("sys.modules", dependencies):
            hardware = importlib.import_module("acertezero.hardware")
            with patch.object(hardware, "Pi5Pixelbuf", FakePixels), patch.object(hardware.time, "sleep"):
                for player, base, pulse in (
                    (1, (1, 48, 13), (4, 192, 52)),
                    (2, (15, 12, 0), (60, 48, 0)),
                ):
                    with self.subTest(player=player):
                        game = AcerteZeroGame(led_count=5, seed=1)
                        strip = hardware.ScoreStrip("data", 5)
                        self.assertEqual(strip.pixels.byteorder, "BGR")
                        transmitted = (base[2], base[1], base[0])
                        physical_rgb = (transmitted[1], transmitted[0], transmitted[2])
                        self.assertEqual(physical_rgb,
                                         (48, 13, 1) if player == 1 else (12, 0, 15))
                        strip.show(game)
                        result = game.hit(game.active_targets[player])
                        strip.show(game, result.claimed_led)
                        self.assertEqual(strip.pixels.frames[-2][result.claimed_led], pulse)
                        self.assertEqual(strip.pixels.frames[-1][result.claimed_led], base)

    def test_gpio_outputs_follow_active_targets_and_turn_off_at_victory(self):
        pixelbuf = ModuleType("adafruit_pixelbuf")
        pixelbuf.PixelBuf = type("PixelBuf", (), {})
        neopixel_write = ModuleType("adafruit_raspberry_pi5_neopixel_write")
        neopixel_write.neopixel_write = lambda *args: None
        digitalio = ModuleType("digitalio")
        ports = {}

        class FakePort:
            def __init__(self, pin):
                self.value = None
                self.direction = None
                ports[pin] = self

            def deinit(self):
                pass

        digitalio.DigitalInOut = FakePort
        digitalio.Direction = type("Direction", (), {"OUTPUT": "output"})
        dependencies = {
            "adafruit_pixelbuf": pixelbuf,
            "adafruit_raspberry_pi5_neopixel_write": neopixel_write,
            "digitalio": digitalio,
        }
        with patch.dict("sys.modules", dependencies):
            hardware = importlib.import_module("acertezero.hardware")
            pins = {Target(player, index): f"J{player}:{index}"
                    for player in (1, 2) for index in range(1, 6)}
            lights = hardware.DigitalTargetLights(pins)
            display = hardware.GameDisplay(None, lights)
            game = AcerteZeroGame(led_count=2, targets_per_player=5, seed=1)
            display.show(game)
            self.assertEqual({pin for pin, port in ports.items() if port.value},
                             {f"J{target.player}:{target.number}" for target in game.active_targets.values()})

            game.hit(game.active_targets[1])
            display.show(game)
            self.assertEqual(game.active_targets, {})
            self.assertFalse(any(port.value for port in ports.values()))
            display.close()


    def test_start_animation_sweeps_both_sides_and_reveals_active_targets(self):
        frames = []
        delays = []

        class FakeLights:
            def show(self, active):
                frames.append(active)

        active = (Target(1, 2), Target(2, 3))
        play_start_animation(FakeLights(), 3, active, frame_seconds=0.01, sleep=delays.append)

        self.assertEqual(frames, [
            (Target(1, 1), Target(2, 1)),
            (Target(1, 2), Target(2, 2)),
            (Target(1, 3), Target(2, 3)),
            (Target(1, 2), Target(2, 2)),
            (Target(1, 1), Target(2, 1)),
            (),
            active,
        ])
        self.assertEqual(delays, [0.01] * 6)


class SimulatorTests(unittest.TestCase):
    def test_cli_builds_target_light_mapping_in_target_order(self):
        board = ModuleType("board")
        for pin in (5, 6, 12, 13, 19, 20, 21, 23, 24, 25):
            setattr(board, f"D{pin}", f"gpio-{pin}")
        board.D16 = "strip-gpio"
        hardware = ModuleType("acertezero.hardware")
        captured = {}

        class FakeScoreStrip:
            def __init__(self, pin, count):
                captured["score"] = (pin, count)

        class FakeTargetLights:
            def __init__(self, mapping):
                captured["targets"] = mapping

        class FakeGameDisplay:
            def __init__(self, score, targets):
                captured["display"] = self

        hardware.ScoreStrip = FakeScoreStrip
        hardware.DigitalTargetLights = FakeTargetLights
        hardware.GameDisplay = FakeGameDisplay
        hardware.JudgeButton = object

        with patch.dict("sys.modules", {"board": board, "acertezero.hardware": hardware}):
            with patch("acertezero.simulator.run_simulation") as simulated:
                main([
                    "--leds", "--led-count", "31",
                    "--target-led-pins-j1", "5,6,12,13,19",
                    "--target-led-pins-j2", "20,21,23,24,25",
                ])

        self.assertEqual(captured["score"], ("strip-gpio", 31))
        self.assertEqual(captured["targets"][Target(1, 3)], "gpio-12")
        self.assertEqual(captured["targets"][Target(2, 5)], "gpio-25")
        self.assertEqual(len(captured["targets"]), 10)
        self.assertIs(simulated.call_args.args[1], captured["display"])

    def test_target_led_pin_list_requires_one_pin_per_target(self):
        self.assertEqual(parse_target_led_pins("5, 6, 12", 3), (5, 6, 12))
        with self.assertRaises(ValueError):
            parse_target_led_pins("5,6", 3)
        with self.assertRaises(ValueError):
            parse_target_led_pins("5,x,12", 3)

    def test_uses_start_animation_on_initial_display_and_reset(self):
        game = AcerteZeroGame(led_count=5, seed=1)

        class FakeDisplay:
            def __init__(self):
                self.starts = []
                self.shows = 0

            def start(self, current_game):
                self.starts.append(tuple(current_game.active_targets.values()))

            def show(self, current_game, claimed_led=None):
                self.shows += 1

            def close(self):
                pass

        display = FakeDisplay()
        entries = iter(["r", "s"])
        with redirect_stdout(StringIO()):
            run_simulation(game, display, read=lambda _: next(entries))

        self.assertEqual(len(display.starts), 2)
        self.assertEqual(display.shows, 0)

    def test_simultaneous_input_refreshes_both_target_lights(self):
        game = AcerteZeroGame(led_count=5, seed=1)
        old = game.active_targets.copy()

        class FakeDisplay:
            def __init__(self):
                self.frames = []

            def show(self, current_game, claimed_led=None):
                self.frames.append((tuple(current_game.active_targets.values()), claimed_led))

            def close(self):
                pass

        display = FakeDisplay()
        entries = iter([f"2 {old[2].number}, 1 {old[1].number}", "s"])
        with redirect_stdout(StringIO()):
            run_simulation(game, display, read=lambda _: next(entries))

        self.assertEqual(len(display.frames), 2)
        self.assertEqual(display.frames[0], ((old[1], old[2]), None))
        self.assertNotEqual(display.frames[1][0][0], old[1])
        self.assertNotEqual(display.frames[1][0][1], old[2])
        self.assertEqual(game.hits_by_player, {1: 1, 2: 1})

    def test_updates_led_display_at_start_and_after_valid_hit(self):
        game = AcerteZeroGame(led_count=5, seed=1)
        target_j1 = game.active_targets[1]
        target_j2 = game.active_targets[2]

        class FakeDisplay:
            def __init__(self):
                self.frames = []
                self.closed = False

            def show(self, current_game, claimed_led=None):
                self.frames.append((
                    tuple(current_game.owner_at(i) for i in range(current_game.led_count)),
                    tuple(current_game.active_targets.values()),
                    claimed_led,
                ))

            def close(self):
                self.closed = True

        display = FakeDisplay()
        inactive_number = 1 if target_j1.number != 1 else 2
        entries = iter([
            f"1 {inactive_number}",
            f"1 {target_j1.number}",
            f"2 {target_j2.number}",
            "s",
        ])
        with redirect_stdout(StringIO()):
            run_simulation(game, display, read=lambda _: next(entries))

        self.assertEqual(len(display.frames), 3)
        self.assertEqual(display.frames[0], ((1, 1, 0, 2, 2), (target_j1, target_j2), None))
        self.assertEqual(display.frames[1][0], (1, 1, 1, 2, 2))
        self.assertEqual(display.frames[1][1][1], target_j2)
        self.assertEqual(display.frames[1][2], 2)
        self.assertEqual(display.frames[2][0], (1, 1, 2, 2, 2))
        self.assertEqual(display.frames[2][2], 2)
        self.assertTrue(display.closed)

    def test_keyboard_reset_works_after_victory(self):
        game = AcerteZeroGame(led_count=2, seed=1)

        class FakeDisplay:
            def __init__(self):
                self.frames = []

            def show(self, current_game, claimed_led=None):
                self.frames.append((current_game.player_1_leds, current_game.player_2_leds, current_game.winner))

            def close(self):
                pass

        display = FakeDisplay()
        winning_target = game.active_targets[1]
        entries = iter([f"1 {winning_target.number}", "r", "s"])
        with redirect_stdout(StringIO()):
            run_simulation(game, display, read=lambda _: next(entries))

        self.assertEqual(display.frames, [(1, 1, None), (2, 0, 1), (1, 1, None)])
        self.assertIsNone(game.winner)


class RunnerTests(unittest.TestCase):
    def test_full_arena_refreshes_target_then_clears_all_on_win(self):
        game = AcerteZeroGame(led_count=4, targets_per_player=5, seed=1)
        first_target = game.active_targets[1]
        other_target = game.active_targets[2]

        class FakeInputs:
            def __init__(self):
                self.calls = 0

            def poll(self):
                self.calls += 1
                if self.calls == 1:
                    return [first_target]
                if self.calls == 2:
                    return [game.active_targets[1]]
                raise KeyboardInterrupt

            def close(self):
                pass

        class FakeDisplay:
            def __init__(self):
                self.frames = []

            def start(self, current_game):
                self.frames.append(tuple(current_game.active_targets.values()))

            def show(self, current_game, claimed_led=None):
                self.frames.append(tuple(current_game.active_targets.values()))

            def close(self):
                pass

        display = FakeDisplay()
        with redirect_stdout(StringIO()), patch("acertezero.runner.time.sleep"):
            run(game, FakeInputs(), display)

        self.assertEqual(display.frames[0], (first_target, other_target))
        self.assertEqual(len(display.frames[1]), 2)
        self.assertNotEqual(display.frames[1][0], first_target)
        self.assertEqual(display.frames[1][1], other_target)
        self.assertEqual(display.frames[2], ())
        self.assertEqual(game.winner, 1)


    def test_uses_start_animation_on_initial_display_and_judge_reset(self):
        game = AcerteZeroGame(led_count=5, seed=1)

        class FakeInputs:
            def __init__(self):
                self.calls = 0

            def poll(self):
                self.calls += 1
                if self.calls == 1:
                    return [RESET]
                raise KeyboardInterrupt

            def close(self):
                pass

        class FakeDisplay:
            def __init__(self):
                self.starts = 0
                self.shows = 0

            def start(self, current_game):
                self.starts += 1

            def show(self, current_game, claimed_led=None):
                self.shows += 1

            def close(self):
                pass

        display = FakeDisplay()
        with redirect_stdout(StringIO()):
            run(game, FakeInputs(), display)

        self.assertEqual(display.starts, 2)
        self.assertEqual(display.shows, 0)

    def test_processes_simultaneous_inputs_and_updates_display(self):
        game = AcerteZeroGame(led_count=5, seed=1)
        old = game.active_targets.copy()

        class FakeInputs:
            def __init__(self):
                self.calls = 0

            def poll(self):
                self.calls += 1
                if self.calls == 1:
                    return [old[2], old[1]]
                raise KeyboardInterrupt

            def close(self):
                pass

        class FakeDisplay:
            def __init__(self):
                self.frames = []

            def show(self, current_game, claimed_led=None):
                self.frames.append(tuple(current_game.active_targets.values()))

            def close(self):
                pass

        display = FakeDisplay()
        with redirect_stdout(StringIO()):
            run(game, FakeInputs(), display)
        self.assertEqual(len(display.frames), 2)
        self.assertEqual(game.hits_by_player, {1: 1, 2: 1})
        self.assertNotEqual(display.frames[1][0], old[1])
        self.assertNotEqual(display.frames[1][1], old[2])

    def test_waits_for_judge_after_victory_and_resets(self):
        game = AcerteZeroGame(led_count=2, seed=1)

        class FakeInputs:
            def __init__(self):
                self.calls = 0
                self.closed = False

            def poll(self):
                self.calls += 1
                if self.calls == 1:
                    return [game.active_targets[1]]
                if self.calls == 2:
                    return [RESET]
                raise KeyboardInterrupt

            def close(self):
                self.closed = True

        class FakeDisplay:
            def __init__(self):
                self.frames = []
                self.closed = False

            def show(self, current_game, claimed_led=None):
                self.frames.append((current_game.player_1_leds, current_game.player_2_leds, current_game.winner))

            def close(self):
                self.closed = True

        inputs = FakeInputs()
        display = FakeDisplay()
        with redirect_stdout(StringIO()):
            run(game, inputs, display)

        self.assertEqual(display.frames, [(1, 1, None), (2, 0, 1), (1, 1, None)])
        self.assertTrue(inputs.closed)
        self.assertTrue(display.closed)


if __name__ == "__main__":
    unittest.main()
