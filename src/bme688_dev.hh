#ifndef BME688_DEV_HH
#define BME688_DEV_HH

#include <Arduino.h>
#include <stddef.h>
#include <SD.h>
#include "bme68xLibrary.h"
#include "commMux\commMux.h"
#include <Esp.h>

#include "feather_v2_config.hh"

#define N_KIT_SENS 8
#define NUM_PRES_SENSORS 3 // number of bme688 sensors that are only reading pressure
#define NUM_GAS_READS 3 // the number of samples taken at each heater profile for gas resistance
#define COMPLETE_READ 0xFF
#define MEASURE_DUR 500
#define MEASURE_TIMEOUT 1000*60*5 // five minute timeout if measurements are unable to be gathered

#define REG_CTRL_GAS_0  0x70
#define REG_CTRL_GAS_1  0x71
#define REG_CTRL_HUM    0x72
#define REG_CTRL_MEAS   0x74
#define REG_CONFIG      0x75
#define BME688_HEAT_OFF_BIT     (1U << 3)

Bme68x bme[N_KIT_SENS];
commMux commSetup[N_KIT_SENS];
uint8_t lastMeasindex[N_KIT_SENS] = {0};
bme68xData sensorData[N_KIT_SENS] = {0};
String logFile = "";
String logHeader = "";
uint32_t lastLogged = 0;
uint8_t sensorsRead = 0; //bit mask that keeps track of what sensors have had a valid read
int validReads[8] = {0}; //most refcent valid sensor reads

// Heating cycle specification; Each sensor will have these same settings
// Heater degrees in C at each heating step
uint16_t tempProf[8] = {80, 80, 160, 160, 240, 240, 320, 320};
// Multipliers to shared heating duration for each heating step
uint16_t multProf[8] = { 10,  10,   10,   10,   10,   10,   10,   10};

void bme68x_init() {
    commMuxBegin(Wire, SPI);
    delay(100);
    
    //Enable communication with each of the 8 BME sensors
    for (uint8_t i = 0; i < N_KIT_SENS; i++) {
        commSetup[i] = commMuxSetConfig(Wire, SPI, i, commSetup[i]);
        bme[i].begin(BME68X_SPI_INTF, commMuxRead, commMuxWrite, commMuxDelay, &commSetup[i]);
        if (bme[i].checkStatus()) {
            Serial.println("BME688 init failed: " + String(i));
        }
    }

    for (uint8_t i = 0; i < N_KIT_SENS; i++) {
        // Use default temperature pressure and humidty settings
        bme[i].setTPH();

        // Shared heating duration in milliseconds
        // uint16_t sharedHeatrDur = MEASURE_DUR - (bme[i].getMeasDur(BME68X_PARALLEL_MODE) / INT64_C(1000));
        // bme[i].setHeaterProf(tempProf, multProf, sharedHeatrDur, 8);
    }
}

/**
 * Disable the BME68X gas heater current.
 * Sets heat_off<3> = 1 in ctrl_gas_0 (0x70).
 */
void bme68x_disable_heater_current(Bme68x sensor) {
        uint8_t reg = sensor.readReg(REG_CTRL_GAS_0);
        reg |= BME688_HEAT_OFF_BIT; // set bit 3
        sensor.writeReg(REG_CTRL_GAS_0, reg);
}

void bm68x_disable_all_heater_currents(Bme68x sensorArr[N_KIT_SENS]) {
    for (int i = 0; i < N_KIT_SENS; i++) {
        bme68x_disable_heater_current(bme[i]);
    }
}

void bme68x_enable_heater_current(Bme68x sensor) {
    uint8_t reg = sensor.readReg(REG_CTRL_GAS_0);
    reg &= (uint8_t)~BME688_HEAT_OFF_BIT; // clear bit 3
    sensor.writeReg(REG_CTRL_GAS_0, reg);
}

void bm68x_enable_all_heater_currents(Bme68x sensorArr[N_KIT_SENS]) {
    for (int i = 0; i < N_KIT_SENS; i++) {
        bme68x_enable_heater_current(bme[i]);
    }
}

void bme68x_soft_reset_all() {
    for (uint8_t i = 0; i < N_KIT_SENS; i++) {
        bme[i].softReset();
    }
}

void bme68x_sleep_gas_sensors() {
    DEBUG_PRINT("Sleeping gas Sensors");
    for (uint8_t i = NUM_PRES_SENSORS; i < N_KIT_SENS; i++) {
        bme[i].setOpMode(BME68X_SLEEP_MODE);
    }
}

/**
 * @brief Compute the average of a C-style array (int, float, double, etc.).
 *
 * Usage:
 *   int arr[] = {1, 2, 3};
 *   double avg = average_array(arr);
 */
template <typename T, size_t N>
float average_array(const T (&values)[N], bool remove_max_min = true) {
    if (N == 0) {
        DEBUG_PRINT("\nTRIED TO AVERAGE ARRAY WITH ZERO ELEMENTS.");
        return 0.0; // default return value if N = 0
    }

    float sum = 0.0;
    for (size_t i = 0; i < N; ++i) {
        sum += static_cast<float>(values[i]);
    }

    if (remove_max_min && N > 3) {
        // Find min and max
        float min_val = static_cast<float>(values[0]);
        float max_val = static_cast<float>(values[0]);

        for (size_t i = 1; i < N; ++i) {
            float v = static_cast<float>(values[i]);
            if (v < min_val) min_val = v;
            if (v > max_val) max_val = v;
        }

        // Remove one instance of min and max from the sum
        sum -= min_val;
        sum -= max_val;

        return sum / static_cast<float>(N - 2);
    }
    else { 
        return sum / static_cast<float>(N);
    }
}

bool bme68x_read_gas_sensors(float *avg_gas_res, float &avg_pressure) {
    DEBUG_PRINT("\nReading from BME688 sensor...");
    bme68xData data[N_KIT_SENS-NUM_PRES_SENSORS];
    float pressure_sum = 0;
    int num_pressure_reads = 0;
    // iterate through each heater profile
    for (uint8_t profile = 0; profile < 8; profile++) {
        // iterate through each sensor and get NUM_GAS_READS readings for the each profile
        // then average to a single value
        for (int i = 0; i < NUM_GAS_READS; i++) {
            float profile_reads[N_KIT_SENS-NUM_PRES_SENSORS] = {0};
            uint32_t dur = 0;
            for (uint8_t sensor = NUM_PRES_SENSORS; sensor < N_KIT_SENS; sensor++) {
                bme[sensor].setHeaterProf(tempProf[profile], MEASURE_DUR);
                bme[sensor].setOpMode(BME68X_FORCED_MODE);
                // determine how long to delay to get readings
                uint32_t current_dur = bme[sensor].getMeasDur();
                if (current_dur > dur) { 
                    dur = current_dur;
                }
            }
            delayMicroseconds(dur*16*MEASURE_DUR/500);
            for (uint8_t sensor = NUM_PRES_SENSORS; sensor < N_KIT_SENS; sensor++) {
                bool sample_collected = false;
                do {
                    if (bme[sensor].fetchData()) {
                        bme[sensor].getData(data[sensor - NUM_PRES_SENSORS]);
                        #ifdef DEBUG
                            // Serial.print("Sensor: " + String(sensor) + ", ");
                            // Serial.print("Profile: " + String(profile) + ", ");
                            // Serial.print(String(millis()) + ", ");
                            // Serial.print(String(data[sensor - NUM_PRES_SENSORS].temperature) + ", ");
                            // Serial.print(String(data[sensor - NUM_PRES_SENSORS].pressure) + ", ");
                            // Serial.print(String(data[sensor - NUM_PRES_SENSORS].humidity) + ", ");
                            // Serial.print(String(data[sensor - NUM_PRES_SENSORS].gas_resistance) + ", ");
                            // Serial.println(data[sensor - NUM_PRES_SENSORS].status, HEX);
                        #endif // DEBUG
                        // Prepare data to be averaged, gas sensor reads have additional processing
                        profile_reads[sensor - NUM_PRES_SENSORS] = data[sensor - NUM_PRES_SENSORS].gas_resistance;
                        pressure_sum += data[sensor - NUM_PRES_SENSORS].pressure;
                        num_pressure_reads += 1;
                        sample_collected = true;
                    }
                    else {
                        DEBUG_PRINT("Failed to fetch data for sensor " + String(sensor) + 
                                    " during profile " + String(profile));
                        delay(1);
                    }
                } while (!sample_collected);
            }
            // average the sensor readings for this iteration after droping the min and max value
            avg_gas_res[profile] += average_array(profile_reads, true);
        }
        // divide by number of gas reads that were taken and added to the sum
        avg_gas_res[profile] = avg_gas_res[profile] / NUM_GAS_READS;
    }
    // average the sum of pressures 
    avg_pressure = pressure_sum / num_pressure_reads;
    return true;
}

// bool bme68x_read_gas_sensors_parallel(float *avg_gas_res, float &avg_pressure) {
//     DEBUG_PRINT("\nReading from BME688 sensor (parallel)...");
//     unsigned long timeout_time = millis() + MEASURE_TIMEOUT;
//     uint8_t nFieldsLeft = 0;
//     int16_t indexDiff;
//     bool newLogdata = false;
//     uint32_t assigned_mask = 0;
//     int n_samples_gathered = 0;
//     float samples[N_KIT_SENS-NUM_PRES_SENSORS][8][NUM_GAS_READS] = {-1.0};
//     for (uint8_t i = NUM_PRES_SENSORS; i < N_KIT_SENS; i++) {
//         bme[i].setOpMode(BME68X_PARALLEL_MODE);
//     }
//     delay(MEASURE_DUR);
//     while (n_samples_gathered <= ((N_KIT_SENS-NUM_PRES_SENSORS)*8*3)) {
//         if (millis() > timeout_time) {
//             Serial.print("##ALERT, " + String(CHAMBER_NAME) + " GAS MEASUREMENT TIMED OUT");
//             return false;
//         }
//         for (uint8_t i = NUM_PRES_SENSORS; i < N_KIT_SENS; i++) {
//             if (bme[i].fetchData()) {
//                 do {
//                 nFieldsLeft = bme[i].getData(sensorData[i]);
//                 // DEBUG_PRINT("\nFetched fetched data for " + String(i) + ", num new fields: " + String(nFieldsLeft));
//                     // Check if new data is received
//                     if (sensorData[i].status & BME68X_NEW_DATA_MSK) {
//                         // Inspect miss of data index
//                         indexDiff =
//                             (int16_t)sensorData[i].meas_index - (int16_t)lastMeasindex[i];
//                         if (indexDiff > 1) {
//                             Serial.println("Skip I:" + String(i) +
//                                             ", DIFF:" + String(indexDiff) +
//                                             ", MI:" + String(sensorData[i].meas_index) +
//                                             ", LMI:" + String(lastMeasindex[i]) +
//                                             ", S:" + String(sensorData[i].status, HEX));
//                         }
//                         lastMeasindex[i] = sensorData[i].meas_index;
//                         #ifdef DEBUG
//                             logHeader =  "";
//                             logHeader += millis();
//                             logHeader += ",\ti:";
//                             logHeader += i;
//                             logHeader += ",\ttemp: ";
//                             logHeader += sensorData[i].temperature;
//                             logHeader += ",\tpress: ";
//                             logHeader += sensorData[i].pressure;
//                             logHeader += ",\thum: ";
//                             logHeader += sensorData[i].humidity;
//                             logHeader += ",\tgas_res: ";
//                             logHeader += sensorData[i].gas_resistance;
//                             logHeader += ",\tgas_index: ";
//                             logHeader += sensorData[i].gas_index;
//                             logHeader += ",\tmeas_index: ";
//                             logHeader += sensorData[i].meas_index;
//                             logHeader += ",\tidac: ";
//                             logHeader += sensorData[i].idac;
//                             logHeader += ",\tstatus: ";
//                             logHeader += String(sensorData[i].status, HEX);
//                             logHeader += ",\tgas_mask: ";
//                             logHeader += sensorData[i].status & BME68X_GASM_VALID_MSK;
//                             logHeader += ",\theat_stab_mask: ";
//                             logHeader += sensorData[i].status & BME68X_HEAT_STAB_MSK;
//                             logHeader += "\r\n";
//                             newLogdata = true;
//                             DEBUG_PRINT(logHeader);
//                             #endif // DEBUG
//                             if ((sensorData[i].status & BME68X_GASM_VALID_MSK) && (sensorData[i].status & BME68X_HEAT_STAB_MSK)) { //&& (sensorData[i].status & BME68X_HEAT_STAB_MSK)
//                                 // expect status b0
//                                 // DEBUG_PRINT("FLAGS: Status " + String(sensorData[i].status) + ", GAS " + String(BME68X_GASM_VALID_MSK) + ", Heat " + String(BME68X_HEAT_STAB_MSK));
//                                 DEBUG_PRINT(logHeader);
//                                 n_samples_gathered += 1;
//                             }
//                         // SAVE GAS DATA AT EACH MEASUREMENT INDEX AND AVERAGE PRESSURE 
//                         // AND HUMIDITY WITH DROP OUT FROM GREATEST AND SMALLEST SENSOR AVERAGE 
//                     }
//                 } while (nFieldsLeft);
//             }
//             else {
//                 // if no new samples delay to prevent using unnecessary processor time
//                 delay(50);
//             }
//         }
//     }
//     // iterate through each heater profile step
//     for (uint16_t profile = 0; profile < 8; profile++) {
//          // iterate through each sensor used for gas
//         double profile_avgs[N_KIT_SENS-NUM_PRES_SENSORS] = {0};
//         for (uint8_t sensor = 0; sensor < N_KIT_SENS-NUM_PRES_SENSORS; sensor++) {
//             profile_avgs[sensor] = average_array(samples[sensor][profile], true);
//             // iterate through each sample taken for the profile on current sensor
//         }
//         avg_gas_res[profile] = average_array(profile_avgs, true);
//     }
//     return true;
// }

/**
 * @brief Sets the first NUM_PRES_SENSORS on the BME688 dev board
 * to only report pressure, temperature, and humidity values as fast
 * as they possibly can. Gas resistance will be reported using a dummy
 * place holder value and should not be used.
 * 
 */
void pressure_logger_task(void *pvParameters) {
  (void)pvParameters;

  bme68xData data[NUM_PRES_SENSORS];
  uint32_t sens_delay = 0;

  // Setting the default heater profile configuration for the pressure sensors
  for (uint8_t i = 0; i < NUM_PRES_SENSORS; i++) {
      // Set the default configuration for temperature, pressure and humidity
      bme[i].setTPH();

      // Set the heater configuration to minimize time and current
      bme[i].setHeaterProf(0, 0);
      bme68x_disable_heater_current(bme[i]);
  }

  // stagger the start of each reading so they're evenly spaced apart
  for (uint8_t i = 0; i < NUM_PRES_SENSORS; i++) {
      bme[i].setOpMode(BME68X_FORCED_MODE);
      sens_delay = bme[i].getMeasDur()/NUM_PRES_SENSORS;
      if (sens_delay == 0) sens_delay = 1000;
      vTaskDelay(pdMS_TO_TICKS(sens_delay/1000));
  }

  DEBUG_PRINT("\nPressure logger task Started!");
  
  // get sensor readings
  for (;;) {
    for (uint8_t i = 0; i < NUM_PRES_SENSORS; i++) {
      if (bme[i].fetchData()) {
        bme[i].getData(data[i]);
        // Serial.print("Sensor: " + String(i) + ", ");
        // Serial.print(String(millis()) + ", ");
        // Serial.print(String(data[i].temperature) + ", ");
        // Serial.print(String(data[i].pressure) + ", ");
        // Serial.print(String(data[i].humidity) + ", ");
        // Serial.print(String(data[i].gas_resistance) + ", ");
        // Serial.println(data[i].status, HEX);
        
        Serial.println("##PRESSURE, " + String(CHAMBER_NAME) + ", " + String(data[i].pressure));

        bme[i].setOpMode(BME68X_FORCED_MODE);
        sens_delay = bme[i].getMeasDur()/NUM_PRES_SENSORS;
        if (sens_delay == 0) sens_delay = 1000;
        vTaskDelay(pdMS_TO_TICKS(sens_delay/1000));
      }
    }
  }
}


#endif // BME688_DEV_HH