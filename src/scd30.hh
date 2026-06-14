// Basic demo for readings from Adafruit SCD30
#include <Adafruit_SCD30.h>
#include "feather_v2_config.hh"

Adafruit_SCD30  scd30;

constexpr uint16_t SCD30_MEASUREMENT_INTERVAL_SECONDS = 3;
constexpr unsigned long SCD30_DATA_TIMEOUT_MS =
    (SCD30_MEASUREMENT_INTERVAL_SECONDS + 2UL) * 1000UL;

bool scd30_configure() {
    if (!scd30.setMeasurementInterval(SCD30_MEASUREMENT_INTERVAL_SECONDS)) {
        DEBUG_PRINT("Failed to set SCD30 measurement interval");
        return false;
    }

    if (!scd30.selfCalibrationEnabled(false)) {
        DEBUG_PRINT("Failed to disable SCD30 self calibration");
        return false;
    }

    return true;
}

bool scd30_recover() {
    DEBUG_PRINT("Recovering SCD30 and I2C bus");

    Wire.end();
    delay(10);
    if (!Wire.begin(SDA, SCL, I2C_FREQ)) {
        DEBUG_PRINT("Failed to restart I2C bus");
        return false;
    }
    Wire.setTimeOut(I2C_TIMEOUT_MS);

    scd30.reset();
    delay(2000);

    if (!scd30.startContinuousMeasurement()) {
        DEBUG_PRINT("Failed to restart SCD30 continuous measurement");
        return false;
    }

    return scd30_configure();
}

bool scd30_init() {
    #ifdef DEBUG
        Serial.begin(115200);
        while (!Serial) delay(10);     // will pause Zero, Leonardo, etc until serial console opens
    #endif
        // Try to initialize!
    if (!scd30.begin()) {
        DEBUG_PRINT("Failed to find SCD30 chip");
        return false;
    }
    DEBUG_PRINT("SCD30 Found!");

    if (!scd30_configure()) {
        return false;
    }
    DEBUG_PRINT("SCD30 Measurement Interval: "); 
    DEBUG_PRINT(scd30.getMeasurementInterval()); 
    DEBUG_PRINT(" seconds");
    return true;
}

bool scd30_averaged_read(float &co2_ppm, float &temp_cel, float &rel_hum, int num_readings = 3) {
    if (num_readings <= 0) {
        return false;
    }

    int readings_collected = 0;
    int recovery_attempts = 0;
    unsigned long data_deadline = millis() + SCD30_DATA_TIMEOUT_MS;

    while (readings_collected < num_readings) {
        if (scd30.dataReady()) {
            DEBUG_PRINT("Data available!");
            if (!scd30.read()){
                DEBUG_PRINT("Error reading sensor data");
                if (recovery_attempts >= 1 || !scd30_recover()) {
                    return false;
                }
                recovery_attempts++;
                data_deadline = millis() + SCD30_DATA_TIMEOUT_MS;
                continue;
            }

            // gather new readings and add them to the running average for each reading
            co2_ppm = ((co2_ppm * readings_collected) + scd30.CO2) / (readings_collected + 1);
            temp_cel = ((temp_cel * readings_collected) + scd30.temperature) / (readings_collected + 1);
            rel_hum = ((rel_hum * readings_collected) + scd30.relative_humidity) / (readings_collected + 1);
            readings_collected += 1;
            data_deadline = millis() + SCD30_DATA_TIMEOUT_MS;

            #ifdef DEBUG
                Serial.print("CO2: ");
                Serial.print(scd30.CO2, 3);
                Serial.println(" ppm");

                Serial.print("Temperature: ");
                Serial.print(scd30.temperature);
                Serial.println(" degrees C");
                
                Serial.print("Relative Humidity: ");
                Serial.print(scd30.relative_humidity);
                Serial.println(" %");
            
                Serial.print("Temperature: ");
                Serial.print(scd30.temperature);
                Serial.println(" degrees C");

                Serial.println("");
            #endif
        } else {
            DEBUG_PRINT("SCD30 no new data");

            if (static_cast<long>(millis() - data_deadline) >= 0) {
                if (recovery_attempts >= 1 || !scd30_recover()) {
                    DEBUG_PRINT("SCD30 recovery failed");
                    return false;
                }
                recovery_attempts++;
                data_deadline = millis() + SCD30_DATA_TIMEOUT_MS;
            }
        }

        if (readings_collected < num_readings) {
            delay(500);
        }
    }

    return true;
}
    