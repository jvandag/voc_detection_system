#pragma once

#define I2C_FREQ  400000
#define BAUD_RATE 115200
#define SD_PIN_CS 33 // Chip Select pin for your SD interface, pin 10 on adafruit esp32-s3, pin 33 on adafruit esp32 V2
#define SAMPLE_INTERVAL 5*60*1000 // interval between collecting sensor data in ms
#define CHAMBER_NAME "1"

// Explicit pin defines for the Adafruit esp32 V2 board
// Pinouts for this board must be explicitly defined to work with platformio
#define SDA       22
#define SCL       20
#define MOSI      19
#define MISO      21  
#define SCK       5

/*Chip Select pin for SD interface, pin 10 on adafruit esp32-s3,
pin 33 on adafruit esp32 V2*/
#define CS        33


#if DEBUG // build_flag flag in platformio.ini
    #define DEBUG_PRINT(...) Serial.println(__VA_ARGS__)
#else
    #define DEBUG_PRINT(...) 
#endif