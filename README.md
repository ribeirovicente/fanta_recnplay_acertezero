# AcerteZero

Protótipo de jogo competitivo para dois jogadores com placar em uma fita WS2812B controlada por Raspberry Pi 5.

Cada jogador tem cinco alvos; um alvo de cada lado fica ativo durante a partida. Um acerto válido ocupa um LED neutro ou toma um LED do adversário. As regras estão separadas das entradas físicas para permitir a troca de botões por outros sensores.

## Simulador

Na pasta do projeto, com o ambiente virtual da Pi ativado:

```bash
python -m acertezero.simulator --leds --led-count 31 --judge-button
```

Troque `31` pela quantidade real de LEDs. Digite `1 3`, por exemplo, para acionar o alvo 3 do jogador 1. O botão do juiz fica entre GPIO 22 (pino físico 15) e GND; `r` simula esse botão pelo teclado e `s` encerra. Sem `--leds` e `--judge-button`, a simulação roda em um computador comum.

## Testes e contexto

```bash
python -m unittest discover -s tests -v
```

O histórico técnico, as ligações já validadas e as integrações pendentes estão em [CONTEXTO.md](./CONTEXTO.md).
