"""Simulação de entradas pelo teclado, com exibição opcional na fita real."""

import argparse
import select
import sys
from collections.abc import Callable

from .events import RESET
from .game import Target, AcerteZeroGame
from .interfaces import Display, Inputs


def show(game: AcerteZeroGame) -> None:
    symbols = {0: "⚪", 1: "🔴", 2: "🔵"}
    strip = "".join(symbols[game.owner_at(i)] for i in range(game.led_count))
    print(f"\n{strip}")
    print(f"J1: {game.player_1_leds} | J2: {game.player_2_leds}")
    print(f"Acertos: J1 {game.hits_by_player[1]} | J2 {game.hits_by_player[2]}")
    if game.active_targets:
        for target in game.active_targets.values():
            print(f"ALVO ACESO: jogador {target.player}, alvo {target.number}")
    else:
        print(f"VENCEDOR: jogador {game.winner}")


def read_with_judge(judge: Inputs) -> str:
    """No terminal Linux, espera teclado e botão do juiz ao mesmo tempo."""
    print("Acionamento> ", end="", flush=True)
    while True:
        if RESET in judge.poll():
            print("\nBotão do juiz pressionado.")
            return "r"
        readable, _, _ = select.select([sys.stdin], [], [], 0.01)
        if readable:
            line = sys.stdin.readline()
            if not line:
                raise EOFError
            return line


def run_simulation(
    game: AcerteZeroGame,
    display: Display | None = None,
    read: Callable[[str], str] = input,
    judge: Inputs | None = None,
) -> None:
    """Recebe acertos pelo teclado; a exibição física é independente da entrada."""
    print("Digite jogador e alvo (ex.: 1 3); separe acionamentos simultâneos por vírgula (ex.: 1 3, 2 4). 'r' reinicia; 's' encerra.")
    try:
        if display is not None:
            display.show(game)
        show(game)
        while True:
            try:
                raw = (read_with_judge(judge) if judge is not None else read("Acionamento> ")).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nSimulação encerrada.")
                break
            if raw == "s":
                break
            if raw == "r":
                game.reset()
                print("Nova partida iniciada.")
                if display is not None:
                    display.show(game)
                show(game)
                continue
            try:
                targets = []
                for part in raw.split(","):
                    player, number = map(int, part.split())
                    if player not in (1, 2) or not 1 <= number <= game.targets_per_player:
                        raise ValueError
                    targets.append(Target(player, number))
            except ValueError:
                print(f"Use jogador 1..2 e alvo 1..{game.targets_per_player}; exemplo: 1 3, 2 4.")
                continue
            if game.winner is not None:
                print("Partida encerrada. O juiz pode iniciar outra com 'r' ou pelo botão.")
                continue
            result = game.hit_many(targets)
            print(f"{len(result.accepted_targets)} acerto(s)." if result.accepted_targets else "Alvo apagado: sem ponto.")
            if result.accepted_targets and display is not None:
                display.show(game, result.claimed_led)
            show(game)
    finally:
        if judge is not None:
            judge.close()
        if display is not None:
            display.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Simulador do placar AcerteZero")
    parser.add_argument("--leds", action="store_true", help="mostra o placar na fita da Pi 5, no GPIO 16")
    parser.add_argument("--led-count", type=int, default=31, help="número de LEDs da fita (padrão: 31)")
    parser.add_argument("--judge-button", action="store_true", help="usa botão do juiz no GPIO 22 para reiniciar")
    args = parser.parse_args(argv)

    if args.judge_button and sys.platform != "linux":
        parser.error("--judge-button requer um terminal Linux na Raspberry Pi")

    game = AcerteZeroGame(led_count=args.led_count)
    display = None
    judge = None
    if args.leds or args.judge_button:
        try:
            import board
            from .hardware import JudgeButton, ScoreStrip
        except ImportError as exc:
            raise SystemExit("Bibliotecas da Pi 5 indisponíveis. Ative o ambiente ~/led-env.") from exc
        if args.leds:
            display = ScoreStrip(board.D16, args.led_count)
        if args.judge_button:
            judge = JudgeButton(board.D22)
    run_simulation(game, display, judge=judge)


if __name__ == "__main__":
    main()
