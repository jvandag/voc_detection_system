#include <Arduino.h>
#include <SensirionI2cScd4x.h>
#include <Wire.h>
#include "feather_v2_config.h"

// macro definitions
// make sure that we use the proper definition of NO_ERROR
#ifdef NO_ERROR
#undef NO_ERROR
#endif
#define NO_ERROR 0

SensirionI2cScd4x scd4x;

static char errorMessage[64];
static int16_t error;

static int16_t call_and_check_error(int16_t error_status, String caller_identifier) {
    if (error_status != NO_ERROR) {
        errorToString(error_status, errorMessage, sizeof errorMessage);
        Serial.printf("Error trying to execute %s: %s", caller_identifier, errorMessage);
    }
    return error_status;
}

void scd4x_init() {
    /* needed if not initiated in eternal module 
    {
        Serial.begin(BAUD_RATE);
        while (!Serial) {
            delay(100);
        }
        // Wire.begin(); needed if not initiated in eternal module
    }
    */
    scd4x.begin(Wire, SCD41_I2C_ADDR_62);

    uint64_t serialNumber = 0;
    delay(30);
    // Ensure sensor is in clean state
    call_and_check_error(scd4x.wakeUp(), "wakeUp()");
    call_and_check_error(scd4x.stopPeriodicMeasurement(), "stopPeriodicMeasurement()");
    call_and_check_error(scd4x.reinit(), "reinit()");
    scd4x.setAutomaticSelfCalibrationEnabled(false);
}

void scd4x_single_shot_avg(uint16_t &co2_ppm, float &temp_cel, float &rel_hum) {
  // Take 3 shots back-to-back and average
  uint16_t c1, c2, c3;
  float t1, t2, t3, h1, h2, h3;

  // Discard first reading
  call_and_check_error(scd4x.measureSingleShot(), "measureSingleShot()");

  call_and_check_error(scd4x.measureAndReadSingleShot(c1, t1, h1), "measureAndReadSingleShot()");
  call_and_check_error(scd4x.measureAndReadSingleShot(c2, t2, h2), "measureAndReadSingleShot()");
  call_and_check_error(scd4x.measureAndReadSingleShot(c3, t3, h3), "measureAndReadSingleShot()");
  co2_ppm  = (c1 + c2 + c3) / 3;
  temp_cel = (t1 + t2 + t3) / 3;
  rel_hum  = (h1 + h2 + h3) / 3;
}
