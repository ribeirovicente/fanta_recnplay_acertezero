"""Simulação de entradas pelo teclado, com exibição opcional na fita real."""

import argparse
from collections.abc import Callable

from .game import Target, AcerteZeroGame
from .interfaces import Display


def show(game: AcerteZeroGame) -> None:
    symbols = {0: "⚪", 1: "🔴", 2: "🔵"}
    strip = "".join(symbols[game.owner_at(i)] for i in range(game.led_count))
    print(f"\n{strip}")
    print(f"J1: {game.player_1_leds} | J2: {game.player_2_leds}")
    if game.active_targets:
        for target in game.active_targets.values():
            print(f"ALVO ACESO: jogador {target.player}, alvo {target.number}")
    else:
        print(f"VENCEDOR: jogador {game.winner}")


def run_simulation(
    game: AcerteZeroGame,
    display: Display | None = None,
    read: Callable[[str], str] = input,
) -> None:
    """Recebe acertos pelo teclado; a exibição física é independente da entrada."""
    print("Digite jogador e alvo (ex.: 1 3). 's' encerra.")
    try:
        if display is not None:
            display.show(game)
        show(game)
        while game.winner is None:
            try:
                raw = read("Acionamento> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nSimulação encerrada.")
                break
            if raw == "s":
                break
            try:
                player, number = map(int, raw.split())
                if player not in (1, 2) or not 1 <= number <= game.targets_per_player:
                    raise ValueError
            except ValueError:
                print(f"Use 1..2 para jogador e 1..{game.targets_per_player} para alvo; exemplo: 2 4.")
                continue
            result = game.hit(Target(player, number))
            print("Ponto!" if result.accepted else "Alvo apagado: sem ponto.")
            if result.accepted and display is not None:
                display.show(game, result.claimed_led)
            show(game)
    finally:
        if display is not None:
            display.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Simulador do placar AcerteZero")
    parser.add_argument("--leds", action="store_true", help="mostra o placar na fita da Pi 5, no GPIO 16")
    parser.add_argument("--led-count", type=int, default=31, help="número de LEDs da fita (padrão: 31)")
    args = parser.parse_args(argv)

    game = AcerteZeroGame(led_count=args.led_count)
    display = None
    if args.leds:
        try:
            import board
            from .hardware import ScoreStrip
        except ImportError as exc:
            raise SystemExit("Bibliotecas da Pi 5 indisponíveis. Ative o ambiente ~/led-env.") from exc
        display = ScoreStrip(board.D16, args.led_count)
    run_simulation(game, display)


if __name__ == "__main__":
    main()
