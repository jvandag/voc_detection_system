```C
  Serial.printf("##READING,"
    "%s,"                       // Chamber Name
    "%.1f,%.1f,%.1f,%.1f,"      // BME688 readings row 1
    "%.1f,%.1f,%.1f,%.1f,%.1f," // BME688 readings row 2
    "%.1f,%.1f,%.1f,"           // SCD30 readings
    "%u,%.1f,%.1f,"             // SCD41 readings
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
```