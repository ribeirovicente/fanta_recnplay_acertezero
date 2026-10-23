import unittest
from contextlib import redirect_stdout
from io import StringIO

from acertezero.game import Target, AcerteZeroGame
from acertezero.simulator import run_simulation


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


class SimulatorTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
