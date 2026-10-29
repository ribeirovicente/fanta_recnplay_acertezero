// Firmware de uma placa Modulo Arena Coca-Cola: um Nano por alvo.
// A0: ativacao vinda da Base, nivel baixo = alvo ativo (pull-up de 10k na placa).
// D9: ArdOut, pulso alto de acerto via opto para a Base/Pi.
// D12: dados da fita enderecavel no conector BL (rede legada chamada D9).
// BP1..BP5: cinco piezos do MESMO alvo, em A5,A1,A3,A2,A4.

#include <Adafruit_NeoPixel.h>

const byte TARGET_ENABLE_PIN = A0;
const byte HIT_OUTPUT_PIN = 9;
const byte LED_DATA_PIN = 12;
static_assert(HIT_OUTPUT_PIN != LED_DATA_PIN, "Acerto e fita precisam de pinos distintos.");
const uint16_t TARGET_LED_COUNT = 1;  // Ajustar ao numero real de LEDs em BL.
const byte PLAYER_NUMBER = 1;         // Grave 1 nos cinco Nanos de J1 e 2 nos cinco de J2.
static_assert(PLAYER_NUMBER == 1 || PLAYER_NUMBER == 2, "PLAYER_NUMBER deve ser 1 ou 2.");
// RGB fisico do placar: Pi envia BGR; esta fita recebe GRB via Adafruit_NeoPixel.
const byte TARGET_RED = PLAYER_NUMBER == 1 ? 48 : 12;
const byte TARGET_GREEN = PLAYER_NUMBER == 1 ? 13 : 0;
const byte TARGET_BLUE = PLAYER_NUMBER == 1 ? 1 : 15;
const byte TARGET_BRIGHTNESS = 255;   // Sem escala extra: iguala os valores enviados ao placar.
Adafruit_NeoPixel targetLeds(TARGET_LED_COUNT, LED_DATA_PIN, NEO_GRB + NEO_KHZ800);

const byte SENSOR_COUNT = 5;
const byte PIEZO_PINS[SENSOR_COUNT] = {A5, A1, A3, A2, A4};  // BP1..BP5.
const bool ENABLED[SENSOR_COUNT] = {false, true, false, false, false}; // Desative canais sem piezo montado.
const int TOUCH_DELTA[SENSOR_COUNT] = {25, 25, 50, 50, 25}; // Limiar por BP1..BP5; calibre na montagem real.
const int REARM_DROP = 25;                // Queda mínima em relação à média da batida.
const unsigned long TOUCH_WINDOW_MS = 100;
const unsigned long REFRACTORY_MS = 120;  // Intervalo mínimo entre dois eventos.
const unsigned long STARTUP_MS = 300;     // Ignora transientes após reset.
const unsigned long ACTIVE_SETTLE_MS = 120; // Ignora a transicao ao acender o alvo.
const unsigned long HIT_PULSE_MS = 500;   // Cobre a animacao bloqueante do placar na Pi.
const unsigned long BENCH_TEST_MS = 3000; // Tempo para medir D9 com multimetro.
bool printPeaks = false;  // Comando p alterna diagnostico analogico no Monitor Serial.
const byte CAL_NOISE_WINDOWS = 100;   // 10 s em repouso.
const byte CAL_APPROACH_WINDOWS = 100;  // 10 s aproximando a mão, sem tocar.
const byte CAL_HIT_WINDOWS = 40;      // 4 s para cada batida.
const byte CAL_SETTLE_WINDOWS = 10;   // 1 s para a vibração cessar.
const byte CAL_HIT_COUNT = 5;

enum CalibrationStage { NORMAL, CAL_NOISE, CAL_APPROACH, CAL_HIT, CAL_SETTLE };
CalibrationStage calibrationStage = NORMAL;
byte calibrationIndex = 0;
byte calibrationWindows = 0;
byte calibrationHitsDone = 0;
int calibrationNoiseMin = 1023;
int calibrationNoiseMax = 0;
int calibrationNoiseRise = 0;
int calibrationApproachRise = 0;
int calibrationHitRise = 0;
int calibrationRises[CAL_HIT_COUNT] = {0, 0, 0, 0, 0};
int calibrationPreviousAverage = 0;
bool calibrationHasPrevious = false;
unsigned long calibrationSaturated = 0;
char commandBuffer[4] = {0, 0, 0, 0};
byte commandLength = 0;

bool armed[SENSOR_COUNT] = {true, true, true, true, true};
bool hasPreviousAverage[SENSOR_COUNT] = {false, false, false, false, false};
int previousAverage[SENSOR_COUNT] = {0, 0, 0, 0, 0};
int averageAtHit[SENSOR_COUNT] = {0, 0, 0, 0, 0};
unsigned long lastHitAt[SENSOR_COUNT] = {0, 0, 0, 0, 0};
unsigned long touchWindowAt = 0;
unsigned long startedAt = 0;
unsigned long diagnosticSum[SENSOR_COUNT] = {0, 0, 0, 0, 0};
unsigned int diagnosticCount[SENSOR_COUNT] = {0, 0, 0, 0, 0};
unsigned long reportWindowAt = 0;
int reportMin[SENSOR_COUNT] = {1023, 1023, 1023, 1023, 1023};
int reportPeak[SENSOR_COUNT] = {0, 0, 0, 0, 0};
unsigned long reportSum[SENSOR_COUNT] = {0, 0, 0, 0, 0};
unsigned int reportCount[SENSOR_COUNT] = {0, 0, 0, 0, 0};
unsigned int reportSaturated[SENSOR_COUNT] = {0, 0, 0, 0, 0};
bool targetActive = false;
bool forceActive = false;  // Comando 'a': simula A0 baixo sem dirigir eletricamente o pino.
unsigned long activeSince = 0;
bool hitPulseActive = false;
unsigned long hitPulseSince = 0;
bool reportedThisActivation = false;
bool hasGlobalHit = false;
unsigned long lastGlobalHitAt = 0;
bool outputTestActive = false;
bool ledTestActive = false;
unsigned long outputTestSince = 0;
unsigned long ledTestSince = 0;

void sendHit(byte index, int average) {
  digitalWrite(HIT_OUTPUT_PIN, HIGH);
  hitPulseActive = true;
  hitPulseSince = millis();
  reportedThisActivation = true;
  hasGlobalHit = true;
  lastGlobalHitAt = hitPulseSince;
  Serial.print(F("bateu BP"));
  Serial.print(index + 1);
  Serial.print(F(" media="));
  Serial.println(average);
}

void resetMeasurements() {
  const unsigned long now = millis();
  for (byte i = 0; i < SENSOR_COUNT; i++) {
    hasPreviousAverage[i] = false;
    armed[i] = true;
    diagnosticSum[i] = 0;
    diagnosticCount[i] = 0;
    reportMin[i] = 1023;
    reportPeak[i] = 0;
    reportSum[i] = 0;
    reportCount[i] = 0;
    reportSaturated[i] = 0;
  }
  touchWindowAt = now;
  reportWindowAt = now;
}

void setTargetActive(bool active) {
  if (active == targetActive) return;
  targetActive = active;
  activeSince = millis();
  digitalWrite(HIT_OUTPUT_PIN, LOW);
  hitPulseActive = false;
  reportedThisActivation = false;
  outputTestActive = false;
  ledTestActive = false;
  resetMeasurements();
  targetLeds.fill(active ? targetLeds.Color(TARGET_RED, TARGET_GREEN, TARGET_BLUE) : 0);
  targetLeds.show();
}

void updateHitPulse(unsigned long now) {
  if (hitPulseActive && now - hitPulseSince >= HIT_PULSE_MS) {
    digitalWrite(HIT_OUTPUT_PIN, LOW);
    hitPulseActive = false;
  }
}

void updateBenchTests(unsigned long now) {
  if (outputTestActive && now - outputTestSince >= BENCH_TEST_MS) {
    digitalWrite(HIT_OUTPUT_PIN, LOW);
    outputTestActive = false;
    Serial.println(F("TESTE D9: fim, nivel baixo."));
  }
  if (ledTestActive && now - ledTestSince >= BENCH_TEST_MS) {
    targetLeds.clear();
    targetLeds.show();
    ledTestActive = false;
    Serial.println(F("TESTE BL: fim, LEDs apagados."));
  }
}

void startBenchTest(bool leds) {
  if (calibrationStage != NORMAL || targetActive
      || outputTestActive || ledTestActive || hitPulseActive) {
    Serial.println(F("TESTE: desative o alvo e aguarde o fim da calibracao/outro teste."));
    return;
  }
  if (leds) {
    ledTestActive = true;
    ledTestSince = millis();
    targetLeds.fill(targetLeds.Color(TARGET_RED, TARGET_GREEN, TARGET_BLUE));
    targetLeds.show();
    Serial.println(F("TESTE BL: LEDs acesos por 3 s em D12."));
  } else {
    outputTestActive = true;
    outputTestSince = millis();
    digitalWrite(HIT_OUTPUT_PIN, HIGH);
    Serial.println(F("TESTE D9: nivel alto por 3 s."));
  }
}

void beginCalibration(byte index) {
  calibrationIndex = index;
  calibrationStage = CAL_NOISE;
  calibrationWindows = 0;
  calibrationHitsDone = 0;
  calibrationNoiseMin = 1023;
  calibrationNoiseMax = 0;
  calibrationNoiseRise = 0;
  calibrationApproachRise = 0;
  calibrationHitRise = 0;
  calibrationHasPrevious = false;
  calibrationSaturated = 0;
  // Começa com uma janela inteira, sem misturar leituras anteriores ao comando.
  for (byte i = 0; i < SENSOR_COUNT; i++) {
    diagnosticSum[i] = 0;
    diagnosticCount[i] = 0;
  }
  touchWindowAt = millis();
  Serial.print(F("CAL: sensor BP"));
  Serial.print(index + 1);
  Serial.println(F("; mantenha todos os alvos parados por 10 s."));
}

void endCalibration() {
  calibrationStage = NORMAL;
  resetMeasurements();
}

void finishCalibration() {
  int weakestHit = 1023;
  Serial.print(F("CAL: repouso medias min/max="));
  Serial.print(calibrationNoiseMin);
  Serial.print('/');
  Serial.print(calibrationNoiseMax);
  Serial.print(F("; maior subida sem toque="));
  Serial.print(calibrationNoiseRise);
  Serial.print(F("; maior subida ao aproximar a mao="));
  Serial.print(calibrationApproachRise);
  Serial.print(F("; amostras em 1023="));
  Serial.println(calibrationSaturated);
  Serial.print(F("CAL: subidas maximas das 5 batidas="));
  for (byte i = 0; i < CAL_HIT_COUNT; i++) {
    if (i != 0) Serial.print(',');
    Serial.print(calibrationRises[i]);
    if (calibrationRises[i] < weakestHit) weakestHit = calibrationRises[i];
  }
  Serial.println();

  // A aproximação sem contato também precisa ficar abaixo do limiar.
  const int interferenceRise = max(calibrationNoiseRise, calibrationApproachRise);
  const int interferenceMargin = max(5, interferenceRise / 2);
  const int safeInterference = interferenceRise + interferenceMargin;
  if (weakestHit <= safeInterference) {
    Serial.println(F("CAL: sem limiar confiavel: ruido/aproximacao e batidas se sobrepoem, ou alguma batida nao foi capturada."));
    Serial.println(F("CAL: revise montagem, repita com batidas tipicas ou reduza a janela de 100 ms."));
  } else {
    const int suggestion = safeInterference + (weakestHit - safeInterference) / 2;
    Serial.print(F("CAL: sugestao TOUCH_DELTA["));
    Serial.print(calibrationIndex);
    Serial.print(F("] = "));
    Serial.print(suggestion);
    Serial.println(F("; copie o valor para o array e grave o sketch novamente."));
  }
  if (calibrationSaturated > 0) {
    Serial.println(F("CAL: houve leitura 1023; verifique protecao eletrica, o limiar nao limita tensao."));
  }
  endCalibration();
}

void processCalibrationWindow(int average) {
  int rise = 0;
  if (calibrationHasPrevious && average > calibrationPreviousAverage) {
    rise = average - calibrationPreviousAverage;
  }
  calibrationPreviousAverage = average;
  calibrationHasPrevious = true;

  if (calibrationStage == CAL_NOISE) {
    calibrationNoiseMin = min(calibrationNoiseMin, average);
    calibrationNoiseMax = max(calibrationNoiseMax, average);
    calibrationNoiseRise = max(calibrationNoiseRise, rise);
    if (++calibrationWindows >= CAL_NOISE_WINDOWS) {
      calibrationStage = CAL_APPROACH;
      calibrationWindows = 0;
      Serial.println(F("CAL: por 10 s, aproxime e afaste a mao/dedo repetidamente SEM TOCAR no alvo ou fios."));
    }
  } else if (calibrationStage == CAL_APPROACH) {
    calibrationApproachRise = max(calibrationApproachRise, rise);
    if (++calibrationWindows >= CAL_APPROACH_WINDOWS) {
      calibrationStage = CAL_SETTLE;
      calibrationWindows = 0;
      Serial.println(F("CAL: afaste a mao e aguarde 1 s sem tocar."));
    }
  } else if (calibrationStage == CAL_HIT) {
    calibrationHitRise = max(calibrationHitRise, rise);
    if (++calibrationWindows >= CAL_HIT_WINDOWS) {
      calibrationRises[calibrationHitsDone++] = calibrationHitRise;
      Serial.print(F("CAL: batida "));
      Serial.print(calibrationHitsDone);
      Serial.print(F("/5, maior subida="));
      Serial.println(calibrationHitRise);
      calibrationHitRise = 0;
      calibrationWindows = 0;
      if (calibrationHitsDone == CAL_HIT_COUNT) {
        finishCalibration();
      } else {
        calibrationStage = CAL_SETTLE;
        Serial.println(F("CAL: aguarde 1 s sem tocar."));
      }
    }
  } else if (calibrationStage == CAL_SETTLE) {
    if (++calibrationWindows >= CAL_SETTLE_WINDOWS) {
      calibrationStage = CAL_HIT;
      calibrationWindows = 0;
      if (calibrationHitsDone == 0) {
        Serial.println(F("CAL: bata no alvo 1 vez agora (ate 4 s); use a menor batida que deve contar."));
      } else {
        Serial.println(F("CAL: bata no alvo 1 vez agora (ate 4 s)."));
      }
    }
  }
}

void readSerialCommand() {
  while (Serial.available()) {
    const char ch = Serial.read();
    if (ch == '\r' || ch == '\n') {
      if (commandLength == 2 && commandBuffer[0] == 'c'
          && commandBuffer[1] >= '1' && commandBuffer[1] <= '5') {
        const byte index = commandBuffer[1] - '1';
        if (calibrationStage != NORMAL) {
          Serial.println(F("CAL: calibracao em curso; envie x para cancelar."));
        } else if (!ENABLED[index]) {
          Serial.println(F("CAL: sensor desabilitado em ENABLED."));
        } else {
          beginCalibration(index);
        }
      } else if (commandLength == 1 && commandBuffer[0] == 'x') {
        endCalibration();
        Serial.println(F("CAL: cancelada."));
      } else if (commandLength == 1 && commandBuffer[0] == 's') {
        Serial.print(F("A0 fisico="));
        Serial.print(digitalRead(TARGET_ENABLE_PIN) == LOW ? F("LOW") : F("HIGH"));
        Serial.print(F("; simulacao="));
        Serial.print(forceActive ? F("ON") : F("OFF"));
        Serial.print(F("; alvo="));
        Serial.print(targetActive ? F("ativo") : F("inativo"));
        Serial.print(F("; D9="));
        Serial.println(digitalRead(HIT_OUTPUT_PIN) == HIGH ? F("HIGH") : F("LOW"));
      } else if (commandLength == 1 && commandBuffer[0] == 'a') {
        if (calibrationStage != NORMAL || digitalRead(TARGET_ENABLE_PIN) == LOW) {
          Serial.println(F("TESTE A0: use apenas com A0 fisico HIGH e sem calibracao."));
        } else {
          forceActive = !forceActive;
          setTargetActive(forceActive);
          Serial.println(forceActive ? F("TESTE A0: alvo ativado por software.")
                                     : F("TESTE A0: alvo desativado; controle fisico restaurado."));
        }
      } else if (commandLength == 1 && commandBuffer[0] == 't') {
        startBenchTest(false);
      } else if (commandLength == 1 && commandBuffer[0] == 'l') {
        startBenchTest(true);
      } else if (commandLength == 1 && commandBuffer[0] == 'p') {
        if (calibrationStage != NORMAL) {
          Serial.println(F("P: aguarde o fim da calibracao."));
        } else {
          printPeaks = !printPeaks;
          resetMeasurements();
          Serial.println(printPeaks ? F("P: diagnostico ligado.") : F("P: diagnostico desligado."));
        }
      } else if (commandLength != 0) {
        Serial.println(F("Comandos: s=status, a=alternar alvo, t=D9, l=BL, p=leituras, c1..c5=calibrar BP, x=cancelar."));
      }
      commandLength = 0;
    } else if (commandLength < sizeof(commandBuffer)) {
      commandBuffer[commandLength++] = ch;
    } else {
      commandLength = 0;
    }
  }
}

void setup() {
  startedAt = millis();
  pinMode(TARGET_ENABLE_PIN, INPUT);  // Pull-up de 10k ja existe na placa.
  digitalWrite(HIT_OUTPUT_PIN, LOW);
  pinMode(HIT_OUTPUT_PIN, OUTPUT);
  targetLeds.begin();
  targetLeds.setBrightness(TARGET_BRIGHTNESS);
  targetLeds.clear();
  targetLeds.show();
  resetMeasurements();
  Serial.begin(115200);
  Serial.println("READY");
  Serial.println(F("Comandos + Enter: s=status, a=alternar alvo, t=D9, l=BL, p=leituras, c1..c5=calibrar BP, x=cancelar."));
}

void loop() {
  readSerialCommand();
  const bool physicalActive = digitalRead(TARGET_ENABLE_PIN) == LOW;
  if (physicalActive) forceActive = false;  // A Base assume o controle ao ativar A0.
  setTargetActive(physicalActive || forceActive);
  const unsigned long now = millis();
  updateHitPulse(now);
  updateBenchTests(now);
  if (!targetActive && calibrationStage == NORMAL && !printPeaks) return;

  for (byte index = 0; index < SENSOR_COUNT; index++) {
    if (!ENABLED[index]) {
      continue;  // Entradas sem piezo ficam flutuantes; ativar só após a montagem.
    }
    // Descarta a primeira conversao apos trocar o canal do ADC.
    analogRead(PIEZO_PINS[index]);
    const int sample = analogRead(PIEZO_PINS[index]);
    diagnosticSum[index] += sample;
    diagnosticCount[index]++;
    if (calibrationStage != NORMAL && index == calibrationIndex && sample == 1023) {
      calibrationSaturated++;
    }
    if (printPeaks && calibrationStage == NORMAL) {
      if (sample < reportMin[index]) {
        reportMin[index] = sample;
      }
      if (sample > reportPeak[index]) {
        reportPeak[index] = sample;
      }
      reportSum[index] += sample;
      reportCount[index]++;
      if (sample == 1023) {
        reportSaturated[index]++;
      }
    }
  }

  if (now - touchWindowAt >= TOUCH_WINDOW_MS) {
    const bool calibratingThisWindow = calibrationStage != NORMAL;
    for (byte index = 0; index < SENSOR_COUNT; index++) {
      if (!ENABLED[index] || diagnosticCount[index] == 0) {
        continue;
      }
      const int currentAverage = diagnosticSum[index] / diagnosticCount[index];
      diagnosticSum[index] = 0;
      diagnosticCount[index] = 0;

      if (calibratingThisWindow) {
        if (calibrationStage != NORMAL && index == calibrationIndex) {
          processCalibrationWindow(currentAverage);
        }
        continue;  // A calibracao nao emite eventos H de jogo.
      }

      if (now - startedAt < STARTUP_MS || !hasPreviousAverage[index]) {
        // A primeira média é referência, não uma batida.
        hasPreviousAverage[index] = true;
      } else if (armed[index]
                 && currentAverage - previousAverage[index] > TOUCH_DELTA[index]) {
        armed[index] = false;
        averageAtHit[index] = currentAverage;
        lastHitAt[index] = now;
        if (targetActive && now - activeSince >= ACTIVE_SETTLE_MS
            && !hitPulseActive
            && !reportedThisActivation
            && (!hasGlobalHit || now - lastGlobalHitAt >= REFRACTORY_MS)) {
          sendHit(index, currentAverage);
        }
      } else if (!armed[index]
                 && now - lastHitAt[index] >= REFRACTORY_MS
                 && currentAverage <= averageAtHit[index] - REARM_DROP) {
        armed[index] = true;
      }
      previousAverage[index] = currentAverage;
    }
    touchWindowAt = now;
  }

  if (printPeaks && calibrationStage == NORMAL && now - reportWindowAt >= 100) {
    for (byte index = 0; index < SENSOR_COUNT; index++) {
      if (!ENABLED[index]) {
        continue;
      }
      if (reportCount[index] == 0) {
        continue;
      }
      Serial.print("P,BP");
      Serial.print(index + 1);
      Serial.print(',');
      Serial.print(reportMin[index]);
      Serial.print(',');
      Serial.print(reportSum[index] / reportCount[index]);
      Serial.print(',');
      Serial.print(reportPeak[index]);
      Serial.print(',');
      Serial.print(reportSaturated[index]);
      Serial.print(',');
      Serial.println(reportCount[index]);
      reportMin[index] = 1023;
      reportPeak[index] = 0;
      reportSum[index] = 0;
      reportCount[index] = 0;
      reportSaturated[index] = 0;
    }
    reportWindowAt = now;
  }
}
