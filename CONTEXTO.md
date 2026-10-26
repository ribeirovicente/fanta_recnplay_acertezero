# Contexto do projeto AcerteZero

O AcerteZero é um jogo competitivo para dois jogadores. Uma fita WS2812B mostra o território de cada um, enquanto cada jogador tem cinco alvos. Este arquivo registra o protótipo implementado e as decisões de hardware ainda necessárias.

## Hardware já validado

- Raspberry Pi 5 com Raspberry Pi OS e ambiente virtual Python em `~/led-env`.
- Fita WS2812B controlada pelo GPIO 16 (pino físico 36), usando `Adafruit-Blinka-Raspberry-Pi5-Neopixel` e `adafruit-circuitpython-pixelbuf`.
- Fita alimentada por fonte externa de 5 V. O negativo da fonte, o GND da fita e o GND da Pi precisam estar interligados. A fita foi testada primeiro com Arduino Nano e depois com a Pi 5.
- O programa anterior baseado apenas em `neopixel.NeoPixel` não foi o caminho usado no teste funcional da Pi 5. O adaptador atual usa `adafruit_raspberry_pi5_neopixel_write`.
- O botão do juiz foi configurado para GPIO 22 (pino físico 15), ligado ao GND, com pull-up interno e debounce. Essa ligação ainda precisa ser testada fisicamente na Pi.

## Regras implementadas

- A fita começa dividida igualmente: jogador 1 em vermelho a partir do `DIN`, jogador 2 em azul na outra extremidade. Se a quantidade de LEDs for ímpar, o LED central começa branco e neutro.
- Há um alvo ativo para cada jogador, totalizando dois alvos ativos durante a partida. Cada jogador possui cinco alvos possíveis.
- Um acionamento pontua somente quando corresponde ao alvo ativo daquele jogador. Alvos apagados não alteram o placar.
- Um ponto ocupa primeiro o LED neutro, se houver; depois toma um LED do adversário. Só o alvo do jogador que pontuou é sorteado novamente, evitando repetir imediatamente o mesmo alvo. O alvo do adversário permanece ativo.
- A partida termina quando um jogador ocupa todos os LEDs. Após a vitória, não há alvos ativos. O programa permanece em execução à espera do juiz.
- Um aperto do botão do juiz reinicia a partida a qualquer momento: restaura a divisão inicial, remove o vencedor e sorteia um alvo para cada jogador. É necessário soltar e apertar o botão novamente para outro reinício.
- Entradas detectadas na mesma leitura são validadas juntas contra os alvos que estavam acesos antes da leitura. Entradas repetidas e alvos apagados não geram pontos extras.
- Se os dois jogadores acertarem simultaneamente, ambos registram um acerto e recebem novos alvos. Os avanços opostos se anulam: a divisão da fita permanece igual, inclusive quando há um LED neutro. A ordem de leitura dos botões não favorece nenhum jogador.
- Se apenas um jogador acertar dentro do lote, o placar avança normalmente para ele. O reinício pelo juiz continua tendo prioridade sobre o lote inteiro.
- Quando os LEDs dos alvos estiverem configurados, o início e o reinício fazem uma varredura simultânea dos dois lados (1→5→1), apagam brevemente e revelam os dois novos alvos. Acertos durante a partida apenas atualizam os alvos, sem repetir a varredura.

## Estrutura do código

- [game.py](./acertezero/game.py): regras, estado do placar e validação dos acertos, sem dependências de GPIO.
- [interfaces.py](./acertezero/interfaces.py): contratos de entrada e exibição.
- [hardware.py](./acertezero/hardware.py): adaptadores para fita da Pi 5, botões digitais, botão do juiz e LEDs indicadores dos alvos.
- [target_lights.py](./acertezero/target_lights.py): sequência de início/reinício dos LEDs dos alvos, independente do hardware.
- [events.py](./acertezero/events.py): evento de reinício do juiz, independente dos alvos.
- [runner.py](./acertezero/runner.py): conecta entrada, regras e exibição.
- [simulator.py](./acertezero/simulator.py): acertos digitados no terminal; pode mostrar o placar na fita real.
- [serial_inputs.py](./acertezero/serial_inputs.py): lê os eventos USB dos dois Nanos, valida o jogador por porta e agrupa acionamentos próximos.
- [piezo_game.py](./acertezero/piezo_game.py): executa o jogo com as duas portas, opcionalmente com fita, indicadores de alvos e botão do juiz.
- [piezo_target.ino](./arduino/piezo_target/piezo_target.ino): mesmo firmware nos dois Nanos, com `PLAYER` configurado como 1 ou 2; cada um lê cinco piezos em A0..A4.
- [test_game.py](./tests/test_game.py): testes da divisão da fita, validação dos alvos, pontuação, vitória, reinício e atualização da exibição.
- [test_serial_inputs.py](./tests/test_serial_inputs.py): testes do protocolo serial e da integração com o jogo, sem hardware.

## Como executar

Na pasta que contém o pacote `acertezero`, dentro do ambiente virtual da Pi:

```bash
source ~/led-env/bin/activate
python -m acertezero.simulator --leds --led-count 31 --judge-button
```

Substitua `31` pela quantidade real de LEDs. O simulador mostra no terminal o alvo ativo de cada jogador. Digite `1 3`, por exemplo, para acionar o alvo 3 do jogador 1; digite `1 3, 2 4` para simular dois acionamentos na mesma leitura. O juiz pode pressionar o botão no GPIO 22 ou digitar `r` para reiniciar; `s` encerra. A opção `--judge-button` exige execução em um terminal Linux na Pi. Sem `--leds` e `--judge-button`, a simulação funciona em um computador comum. Para rodar os testes: `python -m unittest discover -s tests -v`.

Para acender os dez indicadores físicos, acrescente `--target-led-pins-j1` e `--target-led-pins-j2` ao comando. Cada opção recebe cinco GPIOs BCM separados por vírgula, na ordem dos alvos 1 a 5; ambas são necessárias. Os pinos devem ser exclusivos e não podem usar o GPIO 16 da fita nem o GPIO 22 do juiz quando este estiver ativo. O mapeamento real ainda depende do circuito. Sem essas opções, a fita continua funcional, mas a animação dos alvos não tem saídas físicas.

## Simultaneidade e fila

O executor atual lê os botões em lotes e processa cada lote de forma atômica. Uma fila FIFO isolada não define o empate: o primeiro evento da fila ganharia prioridade na disputa pelo LED neutro e poderia vencer antes do outro ser avaliado. Para os botões atuais, validar o lote contra um único estado e aplicar uma regra explícita de empate é mais simples e previsível.

Se os alvos passarem a produzir eventos assíncronos, uma fila com captura independente, marca de tempo e uma pequena janela de simultaneidade pode preservar pulsos e agrupar entradas próximas. O tamanho dessa janela deve ser medido com os sensores reais. A animação da fita hoje bloqueia a leitura por 120 ms após um ponto individual. O piloto com Nano detecta o pulso no microcontrolador e o evento enviado fica no buffer serial até a Pi voltar a ler; a simultaneidade entre eventos de Nanos diferentes ainda não é garantida.

## Piloto do piezo

Cada Nano atende aos cinco alvos de um jogador, em A0..A4. Por padrão, somente A0 está habilitado no sketch para montar o circuito gradualmente; os demais canais são habilitados quando recebem seus piezos. Cada sensor usa um resistor de 1 MΩ em paralelo e 10 kΩ em série com a entrada. O firmware envia `H,jogador,alvo,valor` pela USB; a Pi lê as duas portas com `pyserial` e reúne eventos recebidos em até 30 ms no mesmo lote. O comando `python -m acertezero.piezo_game --port-j1 /dev/ttyUSB0 --port-j2 /dev/ttyUSB1 --pilot --leds --led-count 31 --judge-button` testa primeiro o alvo 1 de cada lado. Ajuste as portas e a quantidade de LEDs à montagem. As ligações e a calibração estão no [README.md](./README.md#piezos-um-arduino-nano-por-jogador).

Cada canal do Nano acumula amostras em janelas de 100 ms e calcula `diagnosticSum[index] / diagnosticCount[index]`. Uma subida da média maior que o `TOUCH_DELTA` do canal em relação à janela anterior produz `bateu` no Monitor Serial e o evento digital `H,jogador,alvo,media` para a Pi. O usuário ajustou manualmente o valor inicial de A0 para 25; os demais permanecem em 50 até a calibração. A primeira janela estabelece a referência e não gera toque; a queda não pontua. Após uma batida, o canal rearma somente após 120 ms e uma queda de pelo menos 25 na média. Os primeiros 300 ms após reset são ignorados. Esses valores são pontos de partida, não calibração validada para o alvo real. `PRINT_PEAKS` produz estatísticas separadas de 100 ms para diagnóstico e deve ser desligado durante o jogo. A janela longa reduz ruído rápido, mas pode diluir batidas breves; o ajuste deve comparar as variações de repouso, aproximação sem contato e batidas intencionais.

O sketch aceita `c1` a `c5` pelo Monitor Serial (115200 baud, com nova linha) para calibrar cada alvo habilitado, e `x` para cancelar. Por alvo, mede 10 s de repouso, pede 10 s de aproximação repetida da mão/dedo sem contato, aguarda 1 s e pede cinco batidas em janelas de 4 s, separadas por 1 s. Compara a maior subida de média em repouso **ou durante a aproximação** com a menor subida das cinco batidas, aplica margem à maior interferência e sugere um `TOUCH_DELTA` por índice, que deve ser copiado manualmente para o array e gravado no Nano. Se as faixas se sobrepõem, informa que não há limiar confiável. Durante a calibração não envia `H`; o comando independe de `PRINT_PEAKS`. O procedimento está no [README.md](./README.md#calibração-rápida-depois-de-mudar-a-montagem).

Na calibração de A0, foram relatadas leituras `1023` frequentes após substituir o resistor **em série** de 10 kΩ por 1 MΩ. A ligação recomendada continua sendo **1 MΩ em paralelo com o piezo e 10 kΩ em série até A0**. O diagnóstico `P` mostra mínimo, média, máximo, número de amostras em 1023 e número total de amostras por janela de 100 ms; isso distingue um pico breve de uma entrada presa no máximo. Os valores reais e a proteção elétrica ainda precisam ser validados na bancada.

Sem `--pilot`, o jogo usa os cinco alvos por jogador. Indicadores físicos dos dez alvos podem ser mapeados por `--target-led-pins-j1` e `--target-led-pins-j2`; sem essas opções, os alvos ativos aparecem somente no terminal. A latência da USB e a janela de simultaneidade precisam ser medidas no hardware real. O funcionamento dos piezos na montagem final ainda não foi validado.

## Integração pendente

- Definir a ligação física dos dez LEDs indicadores e passar seu mapeamento pelas opções `--target-led-pins-j1` e `--target-led-pins-j2`. As saídas são ativas em nível alto e exigem resistores ou drivers adequados aos LEDs usados; a Pi não pode alimentar lâmpadas de tensão mais alta diretamente pelos GPIOs.
- Montar e testar os dez circuitos de piezo, distribuídos em cinco entradas analógicas por Nano; `DigitalButtons` continua disponível para uma montagem alternativa com botões.
- Testar o botão do juiz no GPIO 22 e reservar esse pino no futuro mapeamento das entradas e saídas dos alvos.
- Definir a proteção elétrica dos sensores para impactos reais, ligar os indicadores dos alvos e calibrar os limiares individualmente.
- Testar o sistema completo na Pi 5 depois de montar os dez alvos. Os testes automatizados atuais verificam a lógica e a exibição com uma implementação simulada, sem acesso ao hardware.
