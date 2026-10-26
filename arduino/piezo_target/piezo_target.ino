// Grave este mesmo sketch nos dois Nanos, alterando PLAYER para 1 ou 2.
// Cada Nano recebe cinco piezos em A0..A4, alvos 1..5 do seu jogador.
// Protocolo USB serial: H,jogador,alvo,media_adc\n

const byte PLAYER = 1;
const byte TARGET_COUNT = 5;
const byte PIEZO_PINS[TARGET_COUNT] = {A0, A1, A2, A3, A4};
const bool ENABLED[TARGET_COUNT] = {true, false, false, false, false};
const int TOUCH_DELTA[TARGET_COUNT] = {50, 50, 50, 50, 50};  // A0..A4, calibrar separadamente.
const int REARM_DROP = 25;                // Queda mínima em relação à média da batida.
const unsigned long TOUCH_WINDOW_MS = 100;
const unsigned long REFRACTORY_MS = 120;  // Intervalo mínimo entre dois eventos.
const unsigned long STARTUP_MS = 300;     // Ignora transientes após reset/USB.
const bool PRINT_PEAKS = true;  // Diagnóstico: mínimo, média, pico e saturação a cada 100 ms.

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

void setup() {
  startedAt = millis();
  Serial.begin(115200);
  Serial.println("READY");
}

void loop() {
  const unsigned long now = millis();
  for (byte index = 0; index < TARGET_COUNT; index++) {
    if (!ENABLED[index]) {
      continue;  // Entradas sem piezo ficam flutuantes; ativar só após a montagem.
    }
    const int sample = analogRead(PIEZO_PINS[index]);
    diagnosticSum[index] += sample;
    diagnosticCount[index]++;
    if (PRINT_PEAKS) {
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
    for (byte index = 0; index < TARGET_COUNT; index++) {
      if (!ENABLED[index] || diagnosticCount[index] == 0) {
        continue;
      }
      const int currentAverage = diagnosticSum[index] / diagnosticCount[index];
      diagnosticSum[index] = 0;
      diagnosticCount[index] = 0;

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

  if (PRINT_PEAKS && now - reportWindowAt >= 100) {
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
