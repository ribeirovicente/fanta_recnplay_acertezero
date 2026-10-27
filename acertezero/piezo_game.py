"""Executa o jogo com alvos recebidos por USB ou pelos GPIOs das bases."""

import argparse
import sys

from .game import AcerteZeroGame, Target
from .interfaces import show_start
from .runner import run
from .serial_inputs import SerialTargetInputs, TwoPlayerInputs
from .simulator import parse_target_led_pins


class ConsoleDisplay:
    """Mostra os acertos no terminal e, opcionalmente, na fita física."""

    def __init__(self, display=None):
        self.display = display

    def start(self, game: AcerteZeroGame) -> None:
        if self.display is not None:
            show_start(self.display, game)
        self._print(game)

    def show(self, game: AcerteZeroGame, claimed_led: int | None = None) -> None:
        if self.display is not None:
            self.display.show(game, claimed_led)
        self._print(game)

    @staticmethod
    def _print(game: AcerteZeroGame) -> None:
        targets = ", ".join(f"J{t.player}:{t.number}" for t in game.active_targets.values())
        print(
            f"Placar J1={game.player_1_leds} J2={game.player_2_leds} | "
            f"acertos J1={game.hits_by_player[1]} J2={game.hits_by_player[2]} | "
            f"alvos: {targets or 'nenhum'}",
            flush=True,
        )

    def close(self) -> None:
        if self.display is not None:
            self.display.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="AcerteZero com entradas USB ou GPIO por jogador")
    parser.add_argument("--port-j1", help="porta USB do Nano do jogador 1")
    parser.add_argument("--port-j2", help="porta USB do Nano do jogador 2")
    parser.add_argument("--input-gpios-j1", metavar="GPIO,...", help="GPIOs BCM das entradas da Base J1, alvos 1..5")
    parser.add_argument("--input-gpios-j2", metavar="GPIO,...", help="GPIOs BCM das entradas da Base J2, alvos 1..5")
    parser.add_argument("--input-debounce-ms", type=int, default=20,
                        help="tempo estável exigido do pulso GPIO (padrão: 20 ms)")
    parser.add_argument("--led-count", type=int, default=31, help="quantidade de LEDs da fita")
    parser.add_argument("--pilot", action="store_true", help="um alvo por jogador para testar o alvo 1")
    parser.add_argument("--leds", action="store_true", help="acende a fita no GPIO 16")
    parser.add_argument("--judge-button", action="store_true", help="usa o botão do juiz no GPIO 22")
    parser.add_argument("--target-led-pins-j1", metavar="GPIO,...", help="GPIOs BCM que ativam os alvos 1..5 do jogador 1")
    parser.add_argument("--target-led-pins-j2", metavar="GPIO,...", help="GPIOs BCM que ativam os alvos 1..5 do jogador 2")
    args = parser.parse_args(argv)
    serial_mode = args.port_j1 is not None or args.port_j2 is not None
    gpio_mode = args.input_gpios_j1 is not None or args.input_gpios_j2 is not None
    if serial_mode == gpio_mode:
        parser.error("Escolha duas portas USB ou duas listas de GPIOs de entrada.")
    if serial_mode and (args.port_j1 is None or args.port_j2 is None):
        parser.error("Informe as portas USB dos dois jogadores.")
    if gpio_mode and (args.input_gpios_j1 is None or args.input_gpios_j2 is None):
        parser.error("Informe as listas de GPIOs dos dois jogadores.")
    if serial_mode and args.port_j1 == args.port_j2:
        parser.error("Informe duas portas seriais diferentes, uma para cada Nano.")
    if args.input_debounce_ms < 0:
        parser.error("O tempo de debounce não pode ser negativo.")
    if (gpio_mode or args.leds or args.judge_button) and sys.platform != "linux":
        parser.error("Os GPIOs exigem a Raspberry Pi com Linux.")

    game = AcerteZeroGame(args.led_count, targets_per_player=1 if args.pilot else 5)
    input_pins = None
    if gpio_mode:
        try:
            input_pins = {
                1: parse_target_led_pins(args.input_gpios_j1, game.targets_per_player),
                2: parse_target_led_pins(args.input_gpios_j2, game.targets_per_player),
            }
        except ValueError as exc:
            parser.error(str(exc))
        all_inputs = input_pins[1] + input_pins[2]
        if len(set(all_inputs)) != len(all_inputs):
            parser.error("Cada entrada de alvo precisa de um GPIO diferente.")
        if {16, 22}.intersection(all_inputs):
            parser.error("GPIO 16 pertence à fita e GPIO 22 ao botão do juiz.")
    target_pins = None
    if (args.target_led_pins_j1 is None) != (args.target_led_pins_j2 is None):
        parser.error("Informe os GPIOs dos LEDs dos dois jogadores.")
    if args.target_led_pins_j1 is not None:
        if not args.leds:
            parser.error("Os LEDs dos alvos exigem --leds.")
        try:
            target_pins = {
                1: parse_target_led_pins(args.target_led_pins_j1, game.targets_per_player),
                2: parse_target_led_pins(args.target_led_pins_j2, game.targets_per_player),
            }
        except ValueError as exc:
            parser.error(str(exc))
        all_pins = target_pins[1] + target_pins[2]
        if len(set(all_pins)) != len(all_pins):
            parser.error("Cada LED de alvo precisa de um GPIO diferente.")
        reserved = {16} | ({22} if args.judge_button else set())
        if reserved.intersection(all_pins):
            parser.error("GPIO 16 pertence à fita e GPIO 22 ao botão do juiz, quando ativado.")
        if input_pins is not None and set(all_pins).intersection(input_pins[1] + input_pins[2]):
            parser.error("Entradas e saídas dos alvos não podem compartilhar GPIOs.")

    display = None
    judge = None
    if gpio_mode or args.leds or args.judge_button:
        try:
            import board
            from .hardware import DigitalButtons, DigitalTargetLights, GameDisplay, JudgeButton, ScoreStrip
        except ImportError as exc:
            raise SystemExit("Bibliotecas da Pi 5 indisponíveis. Ative o ambiente ~/led-env.") from exc
        if args.leds:
            score = ScoreStrip(board.D16, args.led_count)
            if target_pins is None:
                display = score
            else:
                try:
                    pin_map = {
                        Target(player, index): getattr(board, f"D{pin}")
                        for player, pins in target_pins.items()
                        for index, pin in enumerate(pins, start=1)
                    }
                except AttributeError as exc:
                    parser.error(f"GPIO indisponível nesta placa: {exc}")
                display = GameDisplay(score, DigitalTargetLights(pin_map))
        if args.judge_button:
            judge = JudgeButton(board.D22)

    def open_player(player: int):
        if serial_mode:
            port = args.port_j1 if player == 1 else args.port_j2
            return SerialTargetInputs(port, targets_per_player=game.targets_per_player, expected_player=player)
        pins = input_pins[player]
        try:
            pin_map = {Target(player, index): getattr(board, f"D{pin}")
                       for index, pin in enumerate(pins, start=1)}
        except AttributeError as exc:
            parser.error(f"GPIO de entrada indisponível nesta placa: {exc}")
        return DigitalButtons(pin_map, debounce=args.input_debounce_ms / 1000)

    try:
        first = open_player(1)
    except Exception:
        if judge is not None:
            judge.close()
        if display is not None:
            display.close()
        raise
    try:
        second = open_player(2)
    except Exception:
        first.close()
        if judge is not None:
            judge.close()
        if display is not None:
            display.close()
        raise
    inputs = TwoPlayerInputs(first, second, judge)

    print("Aguardando acertos dos dois jogadores. Pressione Ctrl+C para encerrar.", flush=True)
    run(game, inputs, ConsoleDisplay(display))


if __name__ == "__main__":
    main()
