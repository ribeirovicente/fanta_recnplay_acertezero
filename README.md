# AcerteZero

Protótipo de jogo competitivo para dois jogadores com placar em uma fita WS2812B controlada por Raspberry Pi 5.

Cada jogador tem cinco alvos; um alvo de cada lado fica ativo durante a partida. Um acerto válido ocupa um LED neutro ou toma um LED do adversário. As regras estão separadas das entradas físicas para permitir a troca de botões por outros sensores.

## Simulador

Na pasta do projeto, com o ambiente virtual da Pi ativado:

```bash
python -m acertezero.simulator --leds --led-count 31 --judge-button
```

Troque `31` pela quantidade real de LEDs. Digite `1 3`, por exemplo, para acionar o alvo 3 do jogador 1. Para simular dois acionamentos simultâneos, digite `1 3, 2 4` com os números dos alvos ativos. Se ambos acertarem, os dois alvos mudam e o território permanece igual. O botão do juiz fica entre GPIO 22 (pino físico 15) e GND; `r` simula esse botão pelo teclado e `s` encerra. Sem `--leds` e `--judge-button`, a simulação roda em um computador comum.

## LEDs dos alvos

O simulador aceita opcionalmente `--target-led-pins-j1` e `--target-led-pins-j2`, cada um com cinco números de GPIO BCM separados por vírgula, na ordem dos alvos 1 a 5. Os pinos serão definidos após a montagem; sem essas opções, somente a fita do placar acende. Com os dez LEDs configurados, no início e a cada reinício os dois lados fazem uma varredura 1→5→1, apagam brevemente e então acendem somente os dois alvos sorteados. Após um acerto, os alvos são atualizados sem repetir a animação.

As saídas são digitais ativas em nível alto. Use resistores ou drivers adequados aos indicadores escolhidos; não ligue lâmpadas de 5 V ou 12 V diretamente aos GPIOs. O GPIO 16 está reservado para a fita e o GPIO 22 para o botão do juiz quando `--judge-button` estiver ativo.

## Testes e contexto

```bash
python -m unittest discover -s tests -v
```

O histórico técnico, as ligações já validadas e as integrações pendentes estão em [CONTEXTO.md](./CONTEXTO.md).
