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

## Piezos: um Arduino Nano por jogador

Cada Nano lê cinco piezos em `A0` a `A4`. Grave o mesmo [sketch](./arduino/piezo_target/piezo_target.ino) nas duas placas, com `PLAYER = 1` na primeira e `PLAYER = 2` na segunda. O alvo 1 corresponde a `A0`, o alvo 2 a `A1`, e assim até o alvo 5 em `A4`. Cada placa envia por USB linhas `H,jogador,alvo,leitura`, por exemplo `H,2,3,147`. A [entrada serial](./acertezero/serial_inputs.py) só aceita mensagens do jogador associado àquela porta. O [programa do jogo](./acertezero/piezo_game.py) reúne as duas fontes e o botão do juiz.

### Circuito de cada sensor

Monte **o mesmo circuito dez vezes**, cinco em cada Nano, com a alimentação desligada:

```text
piezo + ──┬── resistor 10 kΩ ── A0/A1/A2/A3/A4 do Nano
          │
       resistor 1 MΩ
          │
piezo - ──┴────────────────── GND do mesmo Nano
```

O resistor de **1 MΩ**, em paralelo com o piezo, oferece um caminho para descarregar a carga gerada pelo impacto. Sem ele, o sinal pode permanecer alto ou instável e gerar leituras erráticas. O valor é o do exemplo oficial de detecção de toque da Arduino. O resistor de **10 kΩ**, em série com a entrada analógica, limita a corrente dos picos positivos e negativos que um piezo pode produzir; ele não fixa a tensão num valor seguro por si só. Para impactos fortes ou fiação longa, adicione proteção/condicionamento apropriados, dimensionados após medir os picos reais. Comece com toques leves. Não ligue o piezo ao pino `5V`: ele gera o próprio sinal. Um resistor não tem polaridade; as marcações `+` e `-` no desenho são dos fios do piezo.

**Não substitua o resistor em série de 10 kΩ por 1 MΩ.** O resistor de 1 MΩ deve continuar **entre os dois fios do piezo**, e o de 10 kΩ entre o fio positivo e `A0` (ou outro canal). Um resistor de 1 MΩ em série não impõe um limite de tensão: a entrada do ADC consome pouca corrente e pode permanecer carregada ou captar ruído. O ADC do ATmega328P é otimizado para uma fonte de impedância de cerca de 10 kΩ ou menos; 1 MΩ em série dificulta a amostragem. Se você fez essa troca, desligue o Nano e restaure os dois resistores nas posições do desenho antes de calibrar.

O sinal do piezo pode oscilar, inclusive abaixo de 0 V e acima de 5 V. O ADC do Nano foi feito para ler tensões entre GND e sua referência, normalmente a alimentação de 5 V. O circuito acima é um ponto de partida para toques leves, não uma proteção validada para pancadas fortes. Antes de usar os alvos em competição, meça o pior impacto esperado (preferencialmente com osciloscópio) e dimensione um estágio de limitação/clamp que mantenha a entrada na faixa permitida. Não confie apenas nos diodos internos do microcontrolador para absorver a energia do piezo.

Cada Nano é alimentado pelo próprio cabo USB conectado à Pi. Não ligue os pinos `5V` dos Nanos à Pi, nem uma saída digital de 5 V do Nano diretamente a GPIOs da Pi. A fita WS2812B mantém sua fonte externa e o GND comum **entre fita, fonte e Pi**, como na montagem já validada; a comunicação Nano↔Pi passa pelos cabos USB.

### Montagem e calibração, em etapas

1. Ligue somente o piezo do alvo 1 em `A0` de cada Nano. No sketch, deixe `ENABLED = {true, false, false, false, false}`. Grave a versão `PLAYER = 1` no Nano J1 e depois mude para `PLAYER = 2` e grave no Nano J2. Na Arduino IDE, escolha a placa **Arduino Nano**, o processador/bootloader compatível com sua placa e a porta correspondente.
2. Teste uma placa de cada vez no Monitor Serial da Arduino IDE em **115200 baud**. Ao tocar o primeiro piezo do J1, espere `bateu` seguido de `H,1,1,media`; no J2, `bateu` seguido de `H,2,1,media`. O Nano ignora os primeiros 300 ms após ligar ou reiniciar. Uma batida válida produz um par de linhas; o evento `H` é o que a Pi entende. Feche o Monitor Serial antes de rodar Python, pois a porta só pode ser aberta por um programa de cada vez.
3. Com `PRINT_PEAKS = true`, observe `P,jogador,alvo,mínimo,média,máximo,saturadas,amostras` a cada 100 ms. Por exemplo, `P,1,1,0,12,1023,1,850` mostra **uma** amostra saturada em 850; não significa que o sinal ficou em 1023 durante toda a janela. O detector também usa médias de **100 ms**, calculadas por `diagnosticSum[index] / diagnosticCount[index]`: se a média subir **mais que o `TOUCH_DELTA` do canal** em relação à janela anterior, conta uma batida. A queda não conta. Após uma batida, espera no mínimo 120 ms e uma queda de pelo menos 25 na média antes de aceitar outra. `TOUCH_DELTA` é um array para ajustar separadamente A0..A4; o valor atual de A0 é 25, ajustado manualmente, e os demais são 50. `TOUCH_WINDOW_MS`, `REARM_DROP` e `REFRACTORY_MS` são comuns aos cinco sensores. Volte `PRINT_PEAKS` para `false` após calibrar: a impressão do diagnóstico serial consome tempo de amostragem. `1023` é o teto do ADC, não uma medida da tensão máxima que o piezo realmente gerou.
4. Acrescente os piezos de `A1` a `A4`, um de cada vez, com seus próprios resistores de 1 MΩ e 10 kΩ. Mude a posição correspondente em `ENABLED` para `true`, grave o sketch novamente e confirme no Monitor Serial que tocar `A3`, por exemplo, emite o alvo 4. Entradas sem sensor devem permanecer desabilitadas: uma entrada analógica solta pode flutuar e criar falsos toques.

#### Calibração rápida depois de mudar a montagem

1. Com a montagem pronta, abra o Monitor Serial em **115200 baud**, selecione **Nova linha** e envie `c1` para o alvo 1 (`c2` a `c5` para os demais alvos habilitados). Calibre um alvo por vez, em cada Nano. Envie `x` para cancelar. O comando funciona mesmo com `PRINT_PEAKS = false`.
2. Mantenha **todos os alvos parados por 10 segundos**. O Nano mede o menor e o maior valor médio e, principalmente, a maior **subida entre médias consecutivas de 100 ms** sem toque. Evite movimentar os cabos nesse período, a menos que queira incluir essa perturbação típica no teste.
3. Quando solicitado, **aproxime e afaste rapidamente a mão ou o dedo por 10 segundos**, repetidas vezes, nas posições em que as pessoas podem passar durante o jogo. Faça isso perto do sensor e dos fios, **sem encostar** em nenhum deles ou no alvo. O Nano mede separadamente a maior subida causada por essa aproximação. Depois, afaste a mão e aguarde a pausa de 1 segundo.
4. Quando aparecer `CAL: bata no alvo`, faça **uma batida em até 4 segundos**, com a menor intensidade que ainda deve contar no jogo. Repita cinco vezes, aguardando a pausa de 1 segundo indicada entre tentativas. O Nano registra a maior subida da média em cada tentativa, sem emitir eventos `H` durante a calibração.
5. Leia `CAL: sugestao TOUCH_DELTA[n] = valor`. O índice `n` começa em zero: alvo 1 → `[0]`, alvo 5 → `[4]`. Copie cada valor para o array `TOUCH_DELTA`, grave o sketch novamente e teste batidas reais e aproximações sem contato. A sugestão fica acima da maior subida entre **repouso e aproximação**, com margem, e abaixo da menor subida das cinco batidas. Se aparecer `sem limiar confiavel`, alguma batida não foi capturada ou as faixas se sobrepõem: confira a montagem, repita o teste e considere ajustar a janela ou o condicionamento do sinal.

A calibração mede a **mesma variação de média** usada pelo detector, mas 10 segundos de repouso e 10 segundos de aproximação não garantem ausência de falsos positivos em todas as condições. Faça o teste com o restante do equipamento ligado e observe o comportamento por mais tempo após aplicar os valores. Se aproximar a mão produzir uma variação semelhante à de uma batida, um único limiar não conseguirá distinguir os dois casos: revise a fiação, a fixação do sensor e o condicionamento do sinal. Se houver amostras em `1023`, confira a proteção elétrica: `TOUCH_DELTA` não limita a tensão no pino.

Fixe cada piezo no alvo de forma repetível, prenda os fios para que não puxem o disco e, se alvos vizinhos vibrarem juntos, afaste ou isole mecanicamente as superfícies antes de compensar apenas com limiares maiores. Teste batidas fracas, fortes e rápidas; uma batida deve gerar uma mensagem, duas batidas separadas pelo intervalo escolhido devem gerar duas, e bater em um alvo não deve acionar outro. Cabos longos perto da alimentação da fita podem captar ruído: mantenha o retorno GND junto do sinal de cada sensor e separe esses cabos dos fios de potência.

Os cinco canais são lidos em sequência por `analogRead()`. A decisão usa a média de **100 ms**. Essa janela pode diluir batidas breves: um pulso curto pode não elevar a média acima do `TOUCH_DELTA` do canal, mesmo que `P` mostre um pico alto. Se isso acontecer, será necessário alongar/capturar o pulso no circuito analógico, reduzir a janela ou rever a taxa de amostragem. Batidas separadas por menos de `REFRACTORY_MS` são propositalmente tratadas como uma só. O valor ADC enviado em `H` é a **média da janela que detectou a batida**, não a força nem a tensão máxima real do piezo.

### Se aparecer 1023 com frequência

1. Confira **qual linha** você está lendo: `P` é um resumo de 100 ms; `H` leva a média de 100 ms que disparou a batida. O sketch inicial enviava a primeira amostra que cruzava um limiar fixo; por isso, seus valores de `H` frequentemente ficavam perto daquele limiar.
2. Com o circuito restaurado e sem tocar no alvo por alguns segundos, observe `mínimo`, `média` e `saturadas`. Se só `máximo` chegar a `1023` ocasionalmente, houve um pico breve. Se `média`, `mínimo` e quase todas as amostras estiverem em `1023`, a entrada está alta de forma contínua: revise a ligação do GND, a posição do resistor em paralelo e se `A0` não foi ligado ao `5V` por engano. Uma entrada já alta no início não deve produzir `bateu` porque a primeira janela apenas estabelece a referência.
3. Para isolar o ADC, desligue o Nano, remova a ligação do piezo e do resistor em série de `A0`, ligue **somente `A0` ao GND por um resistor de 10 kΩ**, religue e observe `P`. Mínimo/média/máximo devem ficar próximos de zero e `saturadas` deve ser zero. Se não ficarem, confira o pino escolhido, os fios e a placa antes de recolocar o piezo.
4. Se o repouso estiver perto de zero, mas toques leves já saturarem, não tente corrigir apenas aumentando `TOUCH_DELTA` nem trocando 10 kΩ por 1 MΩ. O parâmetro decide **quando contar**; não reduz a tensão do pico. Meça o sinal e acrescente um estágio de proteção/limitação dimensionado para esse alvo. Até lá, use somente toques leves no protótipo. Se as variações em repouso ou ao aproximar a mão também passarem do `TOUCH_DELTA` do canal, melhore a fiação/montagem e repita a calibração; se toques legítimos não forem detectados, verifique a duração do pulso e considere uma janela menor.

### Reduzindo falsos positivos

1. **Meça interferências antes de mudar o limiar.** Use a calibração guiada acima; para uma validação mais longa, observe o alvo montado e imóvel por 1–2 minutos, depois repita a aproximação sem contato. Anote a maior subida entre médias `P` consecutivas de 100 ms e quantas janelas têm amostras saturadas. Faça depois várias batidas fracas que *devem* contar e anote a menor subida. Escolha `TOUCH_DELTA` acima da maior variação sem toque, com margem, e abaixo da menor batida desejada. Os valores atuais são pontos de partida. A [Arduino recomenda ajustar o limiar à intensidade observada](https://docs.arduino.cc/built-in-examples/sensors/Knock/).
2. **Corrija a entrada antes de filtrar por software.** Confirme o 1 MΩ em paralelo, o resistor de 10 kΩ em série, o GND do mesmo Nano e os canais não conectados desabilitados. Evite fios analógicos longos próximos aos fios de alimentação da fita; mantenha sinal e retorno próximos. A [Microchip recomenda caminhos analógicos curtos e afastados de sinais digitais rápidos](https://ww1.microchip.com/downloads/en/DeviceDoc/Atmel-7810-Automotive-Microcontrollers-ATmega328P_Datasheet.pdf). Se `P` já muda muito sem toque, elevar o tempo refratário só esconderá sintomas.
3. **Isole vibrações mecânicas.** Fixe o disco e a superfície do alvo firmemente; verifique se movimentos da mesa, alvos vizinhos, objetos soltos ou som forte produzem eventos. A [Adafruit documenta esses falsos acionamentos em sensores de batida](https://learn.adafruit.com/secret-knock-activated-drawer-lock/testing). Separe mecanicamente os alvos antes de compensar apenas elevando o limiar.
4. **Observe o formato das batidas.** A janela de 100 ms pode reduzir a variação da média de impactos curtos. Se o maior ruído em repouso e o menor toque real ficarem na mesma faixa, um limiar único não resolverá. Nesse caso, considere condicionamento analógico para prolongar o sinal ou volte a uma janela menor após estabilizar a montagem. `REFRACTORY_MS` e `REARM_DROP` ajudam contra repetições da mesma batida; não distinguem vibração externa de uma batida intencional.

### Teste na Raspberry Pi

Na Pi, tenha uma cópia atualizada deste repositório e execute os comandos **na pasta do projeto**, com o ambiente Python já usado para a fita. Conecte os dois Nanos por cabos USB de dados. Confira que o sketch gravado no Nano J1 tem `PLAYER = 1` e o do J2 tem `PLAYER = 2`. As portas podem ser `/dev/ttyUSB0` e `/dev/ttyUSB1`, ou `/dev/ttyACM0` e `/dev/ttyACM1`; não presuma qual pertence a cada jogador. Prefira os nomes persistentes em `/dev/serial/by-id/` quando distinguirem as placas. Se as placas iguais não aparecerem com nomes distintos, confira `/dev/serial/by-path/` e mantenha cada Nano na mesma porta USB física.

```bash
source ~/led-env/bin/activate
python -m pip install pyserial
python -m serial.tools.list_ports -v
ls -l /dev/serial/by-id/
ls -l /dev/serial/by-path/
id -nG
```

Se abrir a porta causar `Permission denied`, confira o grupo do dispositivo com `ls -l /dev/ttyUSB0` (troque pelo nome detectado). Se o grupo for `dialout` e ele não aparecer em `id -nG`, execute `sudo usermod -aG dialout "$USER"`, encerre a sessão da Pi e entre novamente antes de testar. Não use `sudo` para executar o jogo nem altere a permissão do dispositivo a cada conexão.

Para identificar J1 e J2, abra **uma porta por vez** com `python -m serial.tools.miniterm /dev/ttyUSB0 115200`, toque o piezo e confira se a linha começa com `H,1,` ou `H,2,`. O Nano pode reiniciar ao abrir a porta; espere a mensagem `READY` e os 300 ms de inicialização. Feche o miniterm antes de abrir a mesma porta em outro programa e repita na segunda porta. `P,...`, `bateu` e `CAL:...` são mensagens de diagnóstico; a Pi processa apenas `H,jogador,alvo,media`.

Depois, confira **as duas portas ao mesmo tempo**, sem iniciar a partida:

```bash
python -m acertezero.piezo_monitor --port-j1 /dev/ttyUSB0 --port-j2 /dev/ttyUSB1
```

Substitua os caminhos pelas portas identificadas. Cada batida deve mostrar `Recebido: jogador 1, alvo N` ou `Recebido: jogador 2, alvo N`. O monitor valida o número do jogador em cada porta e aceita alvos 1 a 5, mesmo quando há apenas um piezo montado. Na versão local usada durante a integração, apenas `A4` está habilitado; nesse caso espere `alvo 5`. Encerre com `Ctrl+C` antes de abrir o jogo.

Com apenas `A0` conectado e habilitado em **cada** Nano, faça o teste inicial do jogo no terminal, sem fita:

```bash
python -m acertezero.piezo_game --port-j1 /dev/ttyUSB0 --port-j2 /dev/ttyUSB1 --pilot
```

No modo `--pilot`, há um alvo ativo por jogador, sempre o alvo 1. Toque J1:1 e veja `acertos J1` aumentar; toque J2:1 e veja `acertos J2` aumentar. Quando ambos tocam quase juntos, os dois acertos são registrados e o território fica igual. Se nenhum dos dois pontuar apesar de os Nanos enviarem `H,...`, confira se as portas foram invertidas: o programa rejeita uma mensagem de J2 na porta informada como J1, e vice-versa. Para acender a fita e usar o botão do juiz, acrescente `--leds --led-count 31 --judge-button` (ajuste `31` à fita). O botão continua no GPIO 22; a fita, no GPIO 16. Pressione o botão do juiz e confirme que a divisão inicial reaparece.

**Atenção:** `--pilot` aceita apenas mensagens do alvo 1 (`A0`). Com somente `A4` habilitado, use o monitor acima para testar a recepção serial; para pontuar no modo piloto, habilite e conecte `A0` em cada Nano.

Depois de validar os dez sensores, rode a partida completa **sem** `--pilot`. O terminal mostra um alvo ativo por jogador; toques em alvos apagados não pontuam. Se já tiver ligado os dez indicadores dos alvos aos GPIOs da Pi, acrescente `--target-led-pins-j1` e `--target-led-pins-j2`, com cinco GPIOs BCM em cada lista, na ordem dos alvos 1 a 5. As duas listas são obrigatórias juntas e não podem repetir GPIOs nem usar GPIO 16 ou 22. Sem essas opções, os alvos ativos aparecem apenas no terminal.

```bash
python -m acertezero.piezo_game --port-j1 /dev/ttyUSB0 --port-j2 /dev/ttyUSB1 --leds --led-count 31 --judge-button
```

A Pi agrupa eventos recebidos das duas portas durante 30 ms antes de processar o lote. Isso ajuda a tratar toques próximos como simultâneos, mas não oferece sincronização exata entre os relógios dos Nanos e o agendamento USB/Linux. Para competição com exigência rigorosa de simultaneidade, será necessário medir a latência real e definir uma regra temporal mais precisa.

## Testes e contexto

```bash
python -m unittest discover -s tests -v
```

O histórico técnico, as ligações já validadas e as integrações pendentes estão em [CONTEXTO.md](./CONTEXTO.md).
