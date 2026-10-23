# Contexto do projeto AcerteZero

O AcerteZero é um jogo competitivo para dois jogadores. Uma fita WS2812B mostra o território de cada um, enquanto cada jogador tem cinco alvos. Este arquivo registra o protótipo implementado e as decisões de hardware ainda necessárias.

## Hardware já validado

- Raspberry Pi 5 com Raspberry Pi OS e ambiente virtual Python em `~/led-env`.
- Fita WS2812B controlada pelo GPIO 16 (pino físico 36), usando `Adafruit-Blinka-Raspberry-Pi5-Neopixel` e `adafruit-circuitpython-pixelbuf`.
- Fita alimentada por fonte externa de 5 V. O negativo da fonte, o GND da fita e o GND da Pi precisam estar interligados. A fita foi testada primeiro com Arduino Nano e depois com a Pi 5.
- O programa anterior baseado apenas em `neopixel.NeoPixel` não foi o caminho usado no teste funcional da Pi 5. O adaptador atual usa `adafruit_raspberry_pi5_neopixel_write`.

## Regras implementadas

- A fita começa dividida igualmente: jogador 1 em vermelho a partir do `DIN`, jogador 2 em azul na outra extremidade. Se a quantidade de LEDs for ímpar, o LED central começa branco e neutro.
- Há um alvo ativo para cada jogador, totalizando dois alvos ativos durante a partida. Cada jogador possui cinco alvos possíveis.
- Um acionamento pontua somente quando corresponde ao alvo ativo daquele jogador. Alvos apagados não alteram o placar.
- Um ponto ocupa primeiro o LED neutro, se houver; depois toma um LED do adversário. Só o alvo do jogador que pontuou é sorteado novamente, evitando repetir imediatamente o mesmo alvo. O alvo do adversário permanece ativo.
- A partida termina quando um jogador ocupa todos os LEDs. Após a vitória, não há alvos ativos. Uma nova partida requer reiniciar o programa.
- O tratamento atual do executor descarta um lote em que duas entradas são detectadas simultaneamente. A regra definitiva para empate ainda precisa ser decidida.

## Estrutura do código

- [game.py](./acertezero/game.py): regras, estado do placar e validação dos acertos, sem dependências de GPIO.
- [interfaces.py](./acertezero/interfaces.py): contratos de entrada e exibição.
- [hardware.py](./acertezero/hardware.py): adaptadores para fita da Pi 5, botões digitais e LEDs indicadores dos alvos.
- [runner.py](./acertezero/runner.py): conecta entrada, regras e exibição.
- [simulator.py](./acertezero/simulator.py): acertos digitados no terminal; pode mostrar o placar na fita real.
- [test_game.py](./tests/test_game.py): testes da divisão da fita, validação dos alvos, pontuação, vitória e atualização da exibição.

## Como executar

Na pasta que contém o pacote `acertezero`, dentro do ambiente virtual da Pi:

```bash
source ~/led-env/bin/activate
python -m acertezero.simulator --leds --led-count 31
```

Substitua `31` pela quantidade real de LEDs. O simulador mostra no terminal o alvo ativo de cada jogador. Digite `1 3`, por exemplo, para acionar o alvo 3 do jogador 1. Digite `s` para sair. Sem `--leds`, a simulação funciona sem a fita e pode ser executada em um computador comum. Para rodar os testes: `python -m unittest discover -s tests -v`.

## Integração pendente

- Definir a ligação e o acionamento físico dos dez LEDs indicadores; o simulador atual exibe os alvos ativos no terminal, e `DigitalTargetLights` ainda precisa receber o mapeamento de pinos. O parâmetro `--leds` acende apenas a fita do placar.
- Definir os pinos ou módulo de expansão para as dez entradas. `DigitalButtons` já implementa leitura com pull-up e debounce, mas não há um programa principal com o mapeamento físico.
- Se os botões forem trocados por sensores piezoelétricos, criar outro adaptador de entrada que emita `Target(jogador, número)`. A Pi não possui entradas analógicas no conector GPIO; o sinal do piezo precisa de condicionamento e leitura apropriados antes de chegar à Pi.
- Testar o sistema completo na Pi 5 depois de montar os dez alvos. Os testes automatizados atuais verificam a lógica e a exibição com uma implementação simulada, sem acesso ao hardware.
