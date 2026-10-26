// Grave este mesmo sketch nos dois Nanos, alterando PLAYER para 1 ou 2.
// Cada Nano recebe cinco piezos em A0..A4, alvos 1..5 do seu jogador.
// Protocolo USB serial: H,jogador,alvo,media_adc\n

const byte PLAYER = 1;
const byte TARGET_COUNT = 5;
const byte PIEZO_PINS[TARGET_COUNT] = {A0, A1, A2, A3, A4};
const bool ENABLED[TARGET_COUNT] = {true, false, false, false, false};
const int TOUCH_DELTA[TARGET_COUNT] = {25, 50, 50, 50, 50};  // A0..A4, calibrar separadamente.
const int REARM_DROP = 25;                // Queda mínima em relação à média da batida.
const unsigned long TOUCH_WINDOW_MS = 100;
const unsigned long REFRACTORY_MS = 120;  // Intervalo mínimo entre dois eventos.
const unsigned long STARTUP_MS = 300;     // Ignora transientes após reset/USB.
const bool PRINT_PEAKS = true;  // Diagnóstico: mínimo, média, pico e saturação a cada 100 ms.
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

bool armed[TARGET_COUNT] = {true, true, true, true, true};
bool hasPreviousAverage[TARGET_COUNT] = {false, false, false, false, false};
int previousAverage[TARGET_COUNT] = {0, 0, 0, 0, 0};
int averageAtHit[TARGET_COUNT] = {0, 0, 0, 0, 0};
unsigned long lastHitAt[TARGET_COUNT] = {0, 0, 0, 0, 0};
unsigned long touchWindowAt = 0;
unsigned long startedAt = 0;
unsigned long diagnosticSum[TARGET_COUNT] = {0, 0, 0, 0, 0};
unsigned int diagnosticCount[TARGET_COUNT] = {0, 0, 0, 0, 0};
unsigned long reportWindowAt = 0;
int reportMin[TARGET_COUNT] = {1023, 1023, 1023, 1023, 1023};
int reportPeak[TARGET_COUNT] = {0, 0, 0, 0, 0};
unsigned long reportSum[TARGET_COUNT] = {0, 0, 0, 0, 0};
unsigned int reportCount[TARGET_COUNT] = {0, 0, 0, 0, 0};
unsigned int reportSaturated[TARGET_COUNT] = {0, 0, 0, 0, 0};

void sendHit(byte index, int average) {
  Serial.println("bateu");
  Serial.print("H,");
  Serial.print(PLAYER);
  Serial.print(',');
  Serial.print(index + 1);
  Serial.print(',');
  Serial.println(average);
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
  for (byte i = 0; i < TARGET_COUNT; i++) {
    diagnosticSum[i] = 0;
    diagnosticCount[i] = 0;
  }
  touchWindowAt = millis();
  Serial.print(F("CAL: alvo "));
  Serial.print(index + 1);
  Serial.println(F("; mantenha todos os alvos parados por 10 s."));
}

void endCalibration() {
  calibrationStage = NORMAL;
  for (byte i = 0; i < TARGET_COUNT; i++) {
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
  touchWindowAt = millis();
  reportWindowAt = touchWindowAt;
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
          Serial.println(F("CAL: alvo desabilitado em ENABLED."));
        } else {
          beginCalibration(index);
        }
      } else if (commandLength == 1 && commandBuffer[0] == 'x') {
        endCalibration();
        Serial.println(F("CAL: cancelada."));
      } else if (commandLength != 0) {
        Serial.println(F("CAL: envie c1..c5 para calibrar um alvo ou x para cancelar."));
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
  Serial.begin(115200);
  Serial.println("READY");
  Serial.println(F("CAL: envie c1..c5 + Enter para calibrar um alvo; x + Enter cancela."));
}

void loop() {
  readSerialCommand();
  const unsigned long now = millis();
  for (byte index = 0; index < TARGET_COUNT; index++) {
    if (!ENABLED[index]) {
      continue;  // Entradas sem piezo ficam flutuantes; ativar só após a montagem.
    }
    const int sample = analogRead(PIEZO_PINS[index]);
    diagnosticSum[index] += sample;
    diagnosticCount[index]++;
    if (calibrationStage != NORMAL && index == calibrationIndex && sample == 1023) {
      calibrationSaturated++;
    }
    if (PRINT_PEAKS && calibrationStage == NORMAL) {
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
    for (byte index = 0; index < TARGET_COUNT; index++) {
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
        sendHit(index, currentAverage);
        armed[index] = false;
        averageAtHit[index] = currentAverage;
        lastHitAt[index] = now;
      } else if (!armed[index]
                 && now - lastHitAt[index] >= REFRACTORY_MS
                 && currentAverage <= averageAtHit[index] - REARM_DROP) {
        armed[index] = true;
      }
      previousAverage[index] = currentAverage;
    }
    touchWindowAt = now;
  }

  if (PRINT_PEAKS && calibrationStage == NORMAL && now - reportWindowAt >= 100) {
    for (byte index = 0; index < TARGET_COUNT; index++) {
      if (!ENABLED[index]) {
        continue;
      }
      if (reportCount[index] == 0) {
        continue;
      }
      Serial.print("P,");
      Serial.print(PLAYER);
      Serial.print(',');
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
