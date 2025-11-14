/**
 * Copyright (C) 2021 Bosch Sensortec GmbH
 *
 * SPDX-License-Identifier: BSD-3-Clause
 * 
 */

#include "Arduino.h"
#include "bme68xLibrary.h"
#include "..\commMux\commMux.h"

#ifndef PIN_CS
#define PIN_CS SS
#endif

#define N_KIT_SENS 8
#define SD_PIN_CS 33

Bme68x bme[N_KIT_SENS];
commMux commSetup[N_KIT_SENS];

/**
 * @brief Initializes the sensor and hardware settings
 */
void setup(void)
{
	commMuxBegin(Wire, SPI);
	Serial.begin(115200);
    delay(100);
	
	while (!Serial)
		delay(10);
		
	/* Communication interface set for all the 8 sensors in the development kit */
    for (uint8_t i = 0; i < N_KIT_SENS; i++) {
        commSetup[i] = commMuxSetConfig(Wire, SPI, i, commSetup[i]);
        bme[i].begin(BME68X_SPI_INTF, commMuxRead, commMuxWrite, commMuxDelay,
                    &commSetup[i]);
        if(bme[i].checkStatus()) {
        Serial.println("Initializing sensor " + String(i) + " failed with error " + bme[i].statusString());
        }
    }

      /* Setting the default heater profile configuration */
    for (uint8_t i = 0; i < N_KIT_SENS; i++) {
        bme[i].setTPH();
        /* Heater temperature in degree Celsius as per the suggested heater profile
        */

        /* Set the default configuration for temperature, pressure and humidity */
        bme[i].setTPH();

        /* Set the heater configuration to 300 deg C for 100ms for Forced mode */
        bme[i].setHeaterProf(0, 0);
    }
	

	Serial.println("TimeStamp(ms), Temperature(deg C), Pressure(Pa), Humidity(%), Gas resistance(ohm), Status");
}

bool initial = true;
void loop(void)
{
	bme68xData data[N_KIT_SENS];
    int num_sensors = 3;

    // stagger the start of each reading so they're evenly spaced appart
    if (initial) {
        for (uint8_t i = 0; i < num_sensors; i++) {
            bme[i].setOpMode(BME68X_FORCED_MODE);
            delayMicroseconds(bme[i].getMeasDur()/num_sensors);
        }
        initial = false;
    }

    // get sensor readings
    for (uint8_t i = 0; i < num_sensors; i++) {
        if (bme[i].fetchData())
        {
            bme[i].setOpMode(BME68X_FORCED_MODE);
            delayMicroseconds(bme[i].getMeasDur()/num_sensors);
            bme[i].getData(data[i]);
            Serial.print("Sensor: " + String(i) + ", ");
            Serial.print(String(millis()) + ", ");
            Serial.print(String(data[i].temperature) + ", ");
            Serial.print(String(data[i].pressure) + ", ");
            Serial.print(String(data[i].humidity) + ", ");
            Serial.print(String(data[i].gas_resistance) + ", ");
            Serial.println(data[i].status, HEX);
        }
    }
}