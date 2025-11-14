/**
 * BME688 Devboard Burn-in (24h)
 * - ESP32 Feather + Bosch BME688 Dev Kit (8 sensors, SPI via commMux)
 * - Runs sensors continuously for stabilization ("burn-in")
 * - No logging, no deep sleep. Optional heartbeat prints.
 */

#include "Arduino.h"
#include "bme68xLibrary.h"
#include "commMux\commMux.h"

#include <Esp.h>

// ---------- Config ----------
#define N_KIT_SENS 8
#define PANIC_LED  LED_BUILTIN

// One scan “frame” length (ms). Keep small so heater runs frequently.
#define MEAS_DUR   400

// Total burn-in duration (default 24 hours)
#define BURN_IN_MS (24UL * 60UL * 60UL * 1000UL)

// Print a short status line every N milliseconds (set 0 to silence)
#define STATUS_EVERY_MS 60000UL
// ----------------------------

Bme68x bme_burn_in[N_KIT_SENS];
commMux commSetup_burn_in[N_KIT_SENS];
bme68xData sensorData_burn_in[N_KIT_SENS];

uint32_t t_start = 0;
uint32_t t_last_status = 0;

static void panicLeds()
{
  while (1) {
    digitalWrite(PANIC_LED, HIGH);
    delay(500);
    digitalWrite(PANIC_LED, LOW);
    delay(500);
  }
}

void setup()
{
  Serial.begin(115200);
  pinMode(PANIC_LED, OUTPUT);
  delay(100);

  // Init I2C+SPI mux for dev kit board
  commMuxBegin(Wire, SPI);

  // Bring up all sensors
  for (uint8_t i = 0; i < N_KIT_SENS; i++) {
    commSetup_burn_in[i] = commMuxSetConfig(Wire, SPI, i, commSetup_burn_in[i]);

    bme_burn_in[i].begin(BME68X_SPI_INTF, commMuxRead, commMuxWrite, commMuxDelay, &commSetup_burn_in[i]);
    if (bme_burn_in[i].checkStatus()) {
      Serial.println(String("Init failed on sensor ") + i + ": " + bme_burn_in[i].statusString());
      panicLeds();
    }
  }

  // Configure each sensor
  for (uint8_t i = 0; i < N_KIT_SENS; i++) {
    // Default T/P/H oversampling & filter
    bme_burn_in[i].setTPH();

    // Heater profile (10 steps). Same shape as Bosch example.
    uint16_t tempProf[10] = {320, 100, 100, 100, 200, 200, 200, 320, 320, 320};  // °C
    uint16_t mulProf[10]  = {  5,   2,  10,  30,   5,   5,   5,   5,   5,   5};  // weights

    // Time available for heater inside the MEAS_DUR frame
    uint16_t sharedHeatrDur =
      MEAS_DUR - (uint16_t)(bme_burn_in[i].getMeasDur(BME68X_PARALLEL_MODE) / INT64_C(1000));

    // If MEAS_DUR is very small (or API returns larger conversion time),
    // clamp to a reasonable heater window (e.g., 100 ms)
    if ((int32_t)sharedHeatrDur <= 0) sharedHeatrDur = 100;

    bme_burn_in[i].setHeaterProf(tempProf, mulProf, sharedHeatrDur, 10);
    bme_burn_in[i].setOpMode(BME68X_PARALLEL_MODE);
  }

  t_start = millis();
  t_last_status = t_start;

  Serial.println(F("BME688 burn-in started (target ~24h). Keep board powered. No sleep."));
}

void loop()
{
  // Continuously fetch data so the device keeps cycling the heater profile.
  for (uint8_t i = 0; i < N_KIT_SENS; i++) {
    if (bme_burn_in[i].fetchData()) {
      // Drain the FIFO; we discard data during burn-in
      while (bme_burn_in[i].getData(sensorData_burn_in[i])) {
        // Optionally, check flags if you want to verify stability
        // bool heat_ok = (sensorData_burn_in[i].status & BME68X_HEAT_STAB_MSK);
        // bool gas_ok  = (sensorData_burn_in[i].status & BME68X_GASM_VALID_MSK);
        // (unused here by design)
      }
    }
  }

  // Heartbeat / status print
  if (STATUS_EVERY_MS && (millis() - t_last_status) >= STATUS_EVERY_MS) {
    t_last_status += STATUS_EVERY_MS;
    uint32_t elapsed = millis() - t_start;
    Serial.print(F("[burn-in] elapsed min = "));
    Serial.println(elapsed / 60000UL);
    digitalWrite(PANIC_LED, !digitalRead(PANIC_LED)); // blink slowly
  }

  // End after burn-in window (optional). Comment this block to run indefinitely.
  if ((millis() - t_start) >= BURN_IN_MS) {
    Serial.println(F("Burn-in complete. You can now flash your low-duty-cycle app."));
    // Leave sensors running or halt; here we halt with a slow blink:
    while (1) {
      digitalWrite(PANIC_LED, HIGH); delay(200);
      digitalWrite(PANIC_LED, LOW);  delay(1800);
    }
  }

  // Keep the loop light so the frame timing (MEAS_DUR) is honored by the driver.
  delay(1);
}
