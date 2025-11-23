#include <Arduino.h>
#include "bme688_dev.hh"
#include "scd4x.hh"
#include "as7341.hh"
#include <Esp.h>

#include "feather_v2_config.hh"

TaskHandle_t pressureTaskHandle = nullptr;

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

  bme68x_init();
  scd4x_init();
  as7341_init();
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

  // SCD41 variables
  uint16_t co2_ppm = 0;
  float temperature, relative_humidity = 0;
  
  // AS7341 Variables
  int avg_frequency_vals[10] = {0};
  
  DEBUG_PRINT("\nReading from BME688 gas sensor...");
  bool gas_read_success = bme68x_read_gas_sensors(avg_gas_res, avg_pressure);
  bme68x_sleep_gas_sensors();
    
  DEBUG_PRINT("\nReading from SCD4x sensor...");
  bool co2_read_success = scd4x_single_shot_avg(co2_ppm, temperature, relative_humidity);
  DEBUG_PRINT("CO2 PPM: " + String(co2_ppm) + 
              "\nTemperature: " + String(temperature) +
              "\nRelative Humidity: " + String(relative_humidity));


  DEBUG_PRINT("\nReading from AS7341 light sensor...");
  as7341_averaged_read(avg_frequency_vals, 3);

  // Send sensor readings over serial to be picked up by another devices (Raspbery Pi)
  Serial.printf("##READING, %s, %u, %f, %f, %f, %f, %f, %f, %f, %f, %f,"
    "%f, %f, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d",
    CHAMBER_NAME,
    co2_ppm, temperature, relative_humidity, // SCD41 Readings
    avg_gas_res[0], avg_gas_res[1], avg_gas_res[2], avg_gas_res[3], // BME688 Readings
    avg_gas_res[4], avg_gas_res[5], avg_gas_res[6], avg_gas_res[7], avg_pressure,
    avg_frequency_vals[0], avg_frequency_vals[1], avg_frequency_vals[2], // AS7341 Readings
    avg_frequency_vals[3], avg_frequency_vals[4], avg_frequency_vals[5],
    avg_frequency_vals[6], avg_frequency_vals[7], avg_frequency_vals[8], avg_frequency_vals[9]
  );
    
  unsigned long loop_time = millis() - loop_start_time;
  DEBUG_PRINT("\nLoop Time: " + String(loop_time));
  delay(SAMPLE_INTERVAL-loop_time);
}
