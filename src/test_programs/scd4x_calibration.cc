#include "scd4x_calibration.h"

bool recalibrate(uint16_t reference_ppm) {
    Wire.begin();
    scd4x.begin(Wire, SCD41_I2C_ADDR_62);

    // FRC must be done while *not* measuring
    uint16_t error;
    error = scd4x.stopPeriodicMeasurement();
    delay(500); // per datasheet: wait ~500 ms after stopping

    // Optional: if you changed offsets/altitude/ASC earlier and persisted them,
    // you can reload EEPROM settings with reinit() (requires idle):
    // scd4x.reinit(); delay(20);

    // Run FRC
    uint16_t frc_correction = 0xFFFF;
    error = scd4x.performForcedRecalibration(reference_ppm, frc_correction);
    if (error || frc_correction == 0xFFFF) return false; // FRC failed
    // Disable ASC:
    scd4x.setAutomaticSelfCalibrationEnabled(false);
    // After setting things like ASC state, temp offset, altitude, etc.
    scd4x.persistSettings(); // writes to EEPROM (takes ~800 ms)
    delay(1);
    // Resume your normal mode
    scd4x.startPeriodicMeasurement();
    return true;
}
