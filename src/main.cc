#include <Arduino.h>
// #include <SD.h>
#include "bme688_dev.hh"
#include "scd4x.hh"
#include <Esp.h>

#include "feather_v2_config.hh"

#define MEAS_DUR 300
#define PRESURE_SAMP_RATE 100 // Pressure sample rate in milliseconds
#define NUM_PRES_SENSORS 3

TaskHandle_t pressureTaskHandle = nullptr;
static const uint32_t BME_MEAS_TIME_MS = 10;    // forced-measurement time (depends on oversampling)
static const uint32_t BASE_INTERVAL_MS = 20;    // spacing between ANY two readings (>= BME_MEAS_TIME_MS + margin)


void pressure_logger_task(void *pvParameters);

void setup(void) {
    unsigned long start_time = millis();

    // SCD41 variables
    uint16_t co2_ppm;
    float temperature, relative_humidity;

    // BME688 Dev Kit Variables
    float avg_gas_res, pressure, humidity = 0;
    int num_reads = 0;

    Serial.begin(BAUD_RATE);
    while (!Serial) {
        delay(100);
    }
    SPI.begin(SCK, MISO, MOSI, CS);
    Wire.begin(SDA, SCL, I2C_FREQ);
    
    DEBUG_PRINT("\nGeneral Initialization Complete!");

    // DEBUG_PRINT("\nReading from SCD4x sensor...");
    // scd4x_init();
    // delay(50);
    // scd4x_single_shot_avg(co2_ppm, temperature, relative_humidity);
    // DEBUG_PRINT("CO2 PPM: " + String(co2_ppm) + 
    //             "\nTemperature: " + String(temperature) +
    //             "\nRelative Humidity: " + String(relative_humidity));

    // // Send sensor readings over serial to be picked up by another devices (Raspbery Pi)
    // Serial.printf("##%s, %u, %f, %f", CHAMBER_NAME, co2_ppm, temperature, relative_humidity);
    
    bme68x_init();
    // while(bme68x_read_sensors(avg_gas_res, pressure, humidity, num_reads)) {sleep(0.25);}

    // Calculate sleep time in micro seconds need until next interval
    //uint64_t sleep_time = (SAMPLE_INTERVAL + start_time - millis()) * 1000;
    //esp_sleep_enable_timer_wakeup(sleep_time);
    //esp_deep_sleep_start();

  xTaskCreatePinnedToCore(
    pressure_logger_task,
    "pressureTask",
    4096,
    NULL,
    0,
    &pressureTaskHandle,
    1        // core 0, loop() stays on the default core
  );
}

void loop() { delay(1);
    // SCD41 variables
    uint16_t co2_ppm;
    float temperature, relative_humidity;

    // BME688 Dev Kit Variables
    float avg_gas_res, pressure, humidity = 0;
    int num_reads = 0;

    DEBUG_PRINT("\nReading from SCD4x sensor...");
    scd4x_init();
    delay(50);
    scd4x_single_shot_avg(co2_ppm, temperature, relative_humidity);
    DEBUG_PRINT("CO2 PPM: " + String(co2_ppm) + 
                "\nTemperature: " + String(temperature) +
                "\nRelative Humidity: " + String(relative_humidity));

    // Send sensor readings over serial to be picked up by another devices (Raspbery Pi)
    Serial.printf("##%s, %u, %f, %f", CHAMBER_NAME, co2_ppm, temperature, relative_humidity);
    
    // bme68x_init();
    // delay(1);
    // bme68x_read_sensors(avg_gas_res, pressure, humidity, num_reads);
    // bme68x_soft_reset();
    // delay(30);




  // uint8_t nFieldsLeft = 0;
  // int16_t indexDiff;
  // bool newLogdata = false;
  // /* Control loop for data acquisition - checks if the data is available */
  // if ((millis() - lastLogged) >= MEAS_DUR) {
    
  //   lastLogged = millis();
  //   for (uint8_t i = 0; i < N_KIT_SENS-NUM_PRES_SENSORS; i++) {
  //     if (bme[i].fetchData()) {
        
  //       do {
  //         nFieldsLeft = bme[i].getData(sensorData[i]);
  //         /* Check if new data is received */
  //         if (sensorData[i].status & BME68X_NEW_DATA_MSK) {
  //           /* Inspect miss of data index */
  //           indexDiff =
  //               (int16_t)sensorData[i].meas_index - (int16_t)lastMeasindex[i];
  //           if (indexDiff > 1) {
            
  //             Serial.println("Skip I:" + String(i) +
  //                            ", DIFF:" + String(indexDiff) +
  //                            ", MI:" + String(sensorData[i].meas_index) +
  //                            ", LMI:" + String(lastMeasindex[i]) +
  //                            ", S:" + String(sensorData[i].status, HEX));
  //           //   panicLeds();
  //           }
  //           lastMeasindex[i] = sensorData[i].meas_index;
  //           logHeader =  "";
  //           logHeader += millis();
  //           logHeader += ",\ti:";
  //           logHeader += i;
  //           logHeader += ",\ttemp: ";
  //           logHeader += sensorData[i].temperature;
  //           logHeader += ",\tpress: ";
  //           logHeader += sensorData[i].pressure;
  //           logHeader += ",\thum: ";
  //           logHeader += sensorData[i].humidity;
  //           logHeader += ",\tgas_res: ";
  //           logHeader += sensorData[i].gas_resistance;
  //           logHeader += ",\tgas_index: ";
  //           logHeader += sensorData[i].gas_index;
  //           logHeader += ",\tmeas_index: ";
  //           logHeader += sensorData[i].meas_index;
  //           logHeader += ",\tidac: ";
  //           logHeader += sensorData[i].idac;
  //           logHeader += ",\tstatus: ";
  //           logHeader += String(sensorData[i].status, HEX);
  //           logHeader += ",\tgas_mask: ";
  //           logHeader += sensorData[i].status & BME68X_GASM_VALID_MSK;
  //           logHeader += ",\theat_stab_mask: ";
  //           logHeader += sensorData[i].status & BME68X_HEAT_STAB_MSK;
  //           logHeader += "\r\n";
  //           newLogdata = true;
  //           Serial.println(logHeader);
  //         }
  //       } while (nFieldsLeft);
  //     }
  //   }
  // }

  // if (newLogdata) {
  //   newLogdata = false;

    
  //   // appendFile(logHeader);
  //   logHeader = "";

  // }
}

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
  
  // // get sensor readings
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
        
        Serial.println("##Pressure," + String(data[i].pressure));

        bme[i].setOpMode(BME68X_FORCED_MODE);
        sens_delay = bme[i].getMeasDur()/NUM_PRES_SENSORS;
        if (sens_delay == 0) sens_delay = 1000;
        vTaskDelay(pdMS_TO_TICKS(sens_delay/1000));
      }
      // sens_delay = bme[i].getMeasDur()/NUM_PRES_SENSORS;
      // if (sens_delay == 0) sens_delay = 1000;
      // vTaskDelay(pdMS_TO_TICKS(sens_delay/1000));
      // Serial.println("main loop wait completed");
    }
  }
}
