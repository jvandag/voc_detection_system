// Basic demo for readings from Adafruit SCD30
#include <Adafruit_SCD30.h>
#include "feather_v2_config.hh"

Adafruit_SCD30  scd30;

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

    if (!scd30.setMeasurementInterval(3)) {
        DEBUG_PRINT("Failed to set measurement interval");
        return false;
    }
    DEBUG_PRINT("SCD30 Measurement Interval: "); 
    DEBUG_PRINT(scd30.getMeasurementInterval()); 
    DEBUG_PRINT(" seconds");

    if (!scd30.selfCalibrationEnabled(false)) {
        DEBUG_PRINT("Self calibration is disabled");
    }
    else {
        DEBUG_PRINT("Disabling self calibration");
        if (!scd30.selfCalibrationEnabled(false)) {
            DEBUG_PRINT("Failed to disable self calibration");
        }
        else {
            DEBUG_PRINT("Disabled self calibration");
        }
    }
    return true;
}

bool scd30_averaged_read(float &co2_ppm, float &temp_cel, float &rel_hum, int num_readings = 3) {
    int readings_collected = 0;
    DEBUG_PRINT("avg 1");
    do {
        if (scd30.dataReady()) {
            DEBUG_PRINT("Data available!");
            if (!scd30.read()){
                DEBUG_PRINT("Error reading sensor data");
                return false;
            }
            DEBUG_PRINT("Avg 2");
            // gather new readings and add them to the running average for each reading
            co2_ppm = ((co2_ppm * readings_collected) + scd30.CO2) / (readings_collected + 1);
            temp_cel = ((temp_cel * readings_collected) + scd30.temperature) / (readings_collected + 1);
            rel_hum = ((rel_hum * readings_collected) + scd30.relative_humidity) / (readings_collected + 1);
            DEBUG_PRINT("Avg 3");
            readings_collected += 1;

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
            DEBUG_PRINT("Avg 4");
        } else {
            DEBUG_PRINT("SCD30 no new data");
        }

        delay(1000); // delay a second waiting for new data
        } while (readings_collected <= num_readings);
    DEBUG_PRINT("Avg 5");
    return true;
}