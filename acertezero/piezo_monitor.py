"""Confere os eventos dos dois Nanos sem iniciar a lógica do jogo."""

import argparse
import time

from .serial_inputs import SerialTargetInputs


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Monitora os alvos recebidos dos dois Nanos USB")
    parser.add_argument("--port-j1", required=True, help="porta USB do Nano do jogador 1")
    parser.add_argument("--port-j2", required=True, help="porta USB do Nano do jogador 2")
    args = parser.parse_args(argv)
    if args.port_j1 == args.port_j2:
        parser.error("Informe portas diferentes para os dois Nanos.")

    first = SerialTargetInputs(args.port_j1, expected_player=1)
    try:
        second = SerialTargetInputs(args.port_j2, expected_player=2)
    except Exception:
        first.close()
        raise

    print("Aguardando toques dos dois Nanos. Pressione Ctrl+C para sair.", flush=True)
    try:
        while True:
            for source in (first, second):
                for target in source.poll():
                    print(f"Recebido: jogador {target.player}, alvo {target.number}", flush=True)
            time.sleep(0.01)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            first.close()
        finally:
            second.close()


if __name__ == "__main__":
    main()
