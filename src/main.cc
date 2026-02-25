#include <Arduino.h>
#include "bme688_dev.hh"
#include "scd30.hh"
#include "scd4x.hh"
#include "as7341.hh"
#include <Esp.h>

#include "feather_v2_config.hh"

TaskHandle_t pressureTaskHandle = nullptr;

void setup(void) {

  Serial.begin(BAUD_RATE);
  while (!Serial) {
      delay(100);
  }
  SPI.begin(SCK, MISO, MOSI, CS);
  Wire.begin(SDA, SCL, I2C_FREQ);

  DEBUG_PRINT("Initializing sensors");
  bme68x_init();
  DEBUG_PRINT("Initialized BME688");
  scd30_init();
  DEBUG_PRINT("Initialized SCD30");
  scd4x_init();
  DEBUG_PRINT("Initialized SCD41");
  as7341_init();
  DEBUG_PRINT("Initialized AS7341");
  delay(50);

  xTaskCreatePinnedToCore(
    pressure_logger_task,
    "pressureTask",
    4096,
    NULL,
    0,
    &pressureTaskHandle,
    1        // core 0, loop() stays on the default core
  );
  DEBUG_PRINT("\nGeneral Initialization Complete!");
}

void loop() {
  unsigned long loop_start_time = millis();

  // BME688 Dev Kit Variables
  float avg_gas_res[8] = {0};
  float avg_pressure = 0;

  //SCD30 Variables
  float scd30_co2_ppm = 0.0f;
  float scd30_temp = 0.0f;
  float scd30_rel_hum = 0.0f;

  // SCD41 Variables
  uint16_t scd4x_co2_ppm = 0;
  float scd4x_temp = 0;
  float scd4x_rel_hum = 0;
  
  // AS7341 Variables
  int avg_frequency_vals[10] = {0};
  
  DEBUG_PRINT("\nReading from BME688 gas sensor...");
  bool gas_read_success = bme68x_read_gas_sensors(avg_gas_res, avg_pressure);
  bme68x_sleep_gas_sensors();

  DEBUG_PRINT("\nReading from SCD30 sensor...");
  bool scd30_read_success = false;
  scd30_read_success = scd30_averaged_read(scd30_co2_ppm, scd30_temp, scd30_rel_hum);
  DEBUG_PRINT("CO2 PPM: " + String(scd30_co2_ppm) + 
              "\nTemperature: " + String(scd30_temp) +
              "\nRelative Humidity: " + String(scd30_rel_hum));  

  DEBUG_PRINT("\nReading from SCD4x sensor...");
  bool scd4x_read_success = scd4x_single_shot_avg(scd4x_co2_ppm, scd4x_temp, scd4x_rel_hum);
  DEBUG_PRINT("CO2 PPM: " + String(scd4x_co2_ppm) + 
              "\nTemperature: " + String(scd4x_temp) +
              "\nRelative Humidity: " + String(scd4x_rel_hum));

  DEBUG_PRINT("\nReading from AS7341 light sensor...");
  as7341_averaged_read(avg_frequency_vals, 3);

  // Send sensor readings over serial to be picked up by another devices (Raspbery Pi)
  // Note, this message must be under the UART fifo buffer size (256 bytes for esp32 wroom and many other microcontrollers)
  Serial.printf("##READING,"
    "%s,"                       // Chamber Name
    "%.2f,%.2f,%.2f,%.2f,"      // BME688 readings row 1
    "%.2f,%.2f,%.2f,%.2f,%.2f," // BME688 readings row 2
    "%.2f,%.2f,%.2f,"           // SCD30 readings
    "%u,%.2f,%.2f,"             // SCD41 readings
    "%d,%d,%d,"                 // AS7341 readings row 1
    "%d,%d,%d,"                 // AS7341 readings row 2
    "%d,%d,%d,%d",              // AS7341 readings row 3
    CHAMBER_NAME,
    avg_gas_res[0], avg_gas_res[1], avg_gas_res[2], avg_gas_res[3], // BME688 Readings
    avg_gas_res[4], avg_gas_res[5], avg_gas_res[6], avg_gas_res[7], avg_pressure, // BME688 Readings
    scd30_co2_ppm, scd30_temp, scd30_rel_hum, // SCD30 Readings
    scd4x_co2_ppm, scd4x_temp, scd4x_rel_hum, // SCD41 Readings
    avg_frequency_vals[0], avg_frequency_vals[1], avg_frequency_vals[2], // AS7341 Readings
    avg_frequency_vals[3], avg_frequency_vals[4], avg_frequency_vals[5], // AS7341 Readings
    avg_frequency_vals[6], avg_frequency_vals[7], avg_frequency_vals[8], avg_frequency_vals[9] // AS7341 Readings
  );
    
  unsigned long loop_time = millis() - loop_start_time;
  DEBUG_PRINT("\nLoop Time: " + String(loop_time));
  delay(SAMPLE_INTERVAL-loop_time);
}
