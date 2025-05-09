#include <Arduino.h>
#include <SD.h>
#include "bme68xLibrary.h"
#include "commMux\commMux.h"
#include <Esp.h>

#define N_KIT_SENS 8
#define SD_PIN_CS 33 // Chip Select pin for your SD interface, pin 10 on adafruit esp32-s3, pin 33 on adafruit esp32 V2
#define PANIC_LED LED_BUILTIN
#define PANIC_DUR 5
#define MEAS_DUR 5
#define SAMPLE_NAME "MEDIUM"
#define COMPLETE_READ 0xFF
#define DEBUG true

// Explicit pin defines for the Adafruit esp32 V2 board
#define SDA       22
#define SCL       20
#define I2C_FREQ  400000
#define MOSI      19
#define MISO      21  
#define SCK       5
#define CS        33 // Chip Select pin for your SD interface, pin 10 on adafruit esp32-s3, pin 33 on adafruit esp32 V2


/* Declaration of variables */
Bme68x bme[N_KIT_SENS];
commMux commSetup[N_KIT_SENS];
uint8_t lastMeasindex[N_KIT_SENS] = {0};
bme68xData sensorData[N_KIT_SENS] = {0};
String logFile = "";
String logHeader = "";
uint32_t lastLogged = 0;
uint8_t sensorsRead = 0; //bit mask that keeps track of what sensors have had a valid read
int validReads[8] = {0}; //most refcent valid sensor reads

/*!
 * @brief Loops the built-in LED to indicate an unrecoverable error
 */
static void panicLeds(void) {
  while (1) {
    digitalWrite(PANIC_LED, HIGH);
    delay(1500);
    digitalWrite(PANIC_LED, LOW);
    delay(500);
  }
}

/* Returns an unused file path starting with the sample name*/
String getLogFileName(int postFix = 0) {
  String path = String("/") + String(SAMPLE_NAME) + String(postFix) + String(".csv");
  return SD.exists(path) ? getLogFileName(postFix + 1) : path;
}

static void setSensorHeaters() {
  /* Setting the default heater profile configuration for each sensor */
  for (uint8_t i = 0; i < N_KIT_SENS; i++) {
    //bme[i].softReset();
    bme[i].setTPH();

    // uint16_t tempProf[10] = {320, 100, 100, 100, 200, 200, 200, 320, 320, 320};
    // uint16_t mulProf[10] = {5, 2, 10, 30, 5, 5, 5, 5, 5, 5};
    uint16_t tempProf[8] = {320, 100, 100, 100, 200, 200, 200, 320};
     uint16_t mulProf[8] = {5, 2, 10, 30, 5, 5, 5, 5};

    // Shared heater duration is leftover time after TPH measurement
    uint16_t sharedHeatrDur = MEAS_DUR - (bme[i].getMeasDur(BME68X_PARALLEL_MODE) / INT64_C(1000));

    bme[i].setHeaterProf(tempProf, mulProf, sharedHeatrDur, 8);
    bme[i].setOpMode(BME68X_PARALLEL_MODE);
  }
}

/*!
 * @brief Appends data to the log file
 */
void saveSensorData() {
  File file;

  if (!SD.exists(logFile)) { // create a new file at path doesn't exist
    if (DEBUG) Serial.println("Creating new log file: " + logFile);
    file = SD.open(logFile, FILE_WRITE); //open in write to create a new file
    //file.close(); //the file isn't created on the SD card until it's closed
    String exists = SD.exists(logFile) ? "yes" : "no";
    if (DEBUG) Serial.println("file exists?: " + exists);
  }
  else { //if path file exists append to it rather than write over
    if (DEBUG) Serial.println("Opening existing log file: " + logFile);
    file = SD.open(logFile, FILE_APPEND); 
  }
  if (!file) {
    if (DEBUG) Serial.println("Failed to open file for appending: " + logFile);
    panicLeds();
  }
  String data = SAMPLE_NAME;
  for (int i = 0; i < 8; i++) {
    data += String(",") + String(i) + "," + String(validReads[i]);
  }
  if (file.println(data)) {
    if (DEBUG) Serial.println("Wrote to " + logFile);
  } else {
    if (DEBUG) Serial.println("Write append failed");
  }
  file.close();
}

/*!
 * @brief Configures and initializes hardware and sensors
 */
void setup(void) {
  if (DEBUG) Serial.begin(9600);
  delay(5000);  // Give time for Serial Monitor to connect
  if (DEBUG) Serial.println("Initializing Setup!");
  //yield();
  /* Initiate SPI communication (shared bus for sensor multiplexer) */
  SPI.begin(SCK, MISO, MOSI, CS);
  Wire.begin(SDA, SCL, I2C_FREQ);
  //Wire.setTimeout(100);           // give it a finite ACK timeout (ms)
  commMuxBegin(Wire, SPI);
  if (DEBUG) Serial.println("CommMux Began...");
  pinMode(PANIC_LED, OUTPUT);
  delay(100);

  /* Setting up SD Card */
  if (DEBUG) Serial.println("Initializing SD card...");

  if (!SD.begin(SD_PIN_CS)) {
    if (DEBUG) Serial.println("SD Card not found or initialization failed");
    panicLeds();
  } 
  else {
    if (DEBUG) Serial.println("SD Card found");
  }

  /* Communication interface set for all the 8 sensors in the development kit */
  for (uint8_t i = 0; i < N_KIT_SENS; i++) {
    commSetup[i] = commMuxSetConfig(Wire, SPI, i, commSetup[i]);
    bme[i].begin(BME68X_SPI_INTF, commMuxRead, commMuxWrite, commMuxDelay, &commSetup[i]);
    if (bme[i].checkStatus()) {
      if (DEBUG) Serial.println("Initializing sensor " + String(i) + " failed with error " + bme[i].statusString());
      panicLeds();
    }
  }
    setSensorHeaters();
    logHeader = "";
    logFile = getLogFileName();
    if (DEBUG) Serial.println("Path: " + logFile);
}

/*!
 * @brief Main loop to fetch sensor data and log to file
 */
void loop(void) {
  uint8_t nFieldsLeft = 0;
  int16_t indexDiff;
  bool newLogdata = false;
  /* Control loop for data acquisition - checks if the data is available */
  if ((millis() - lastLogged) >= MEAS_DUR) {
    lastLogged = millis();
    for (uint8_t i = 0; i < N_KIT_SENS; i++) {
      if (bme[i].fetchData() != 0) {
        do {
          nFieldsLeft = bme[i].getData(sensorData[i]);
          if (sensorData[i].status & BME68X_NEW_DATA_MSK) {
            indexDiff = (int16_t)sensorData[i].meas_index - (int16_t)lastMeasindex[i];
            if (indexDiff > 1) {
              if (DEBUG) Serial.println("Skip I:" + String(i) +
                             ", DIFF:" + String(indexDiff) +
                             ", MI:" + String(sensorData[i].meas_index) +
                             ", LMI:" + String(lastMeasindex[i]) +
                             ", S:" + String(sensorData[i].status, HEX));
              panicLeds();
            }

            lastMeasindex[i] = sensorData[i].meas_index;

            if ((sensorData[i].status & BME68X_GASM_VALID_MSK) && (sensorData[i].status & BME68X_HEAT_STAB_MSK)) {
                sensorsRead |= (1 << i); //indicate that the i-th sensor has had a valid reading
                validReads[i] = sensorData[i].gas_resistance;
                logHeader += "Sensor: " + String(i) + ", Gas Res: " + String(sensorData[i].gas_resistance) + 
                          ", Status: " + String(sensorData[i].status, HEX) + (sensorData[i].status & BME68X_GASM_VALID_MSK) + 
                          (sensorData[i].status & BME68X_HEAT_STAB_MSK) + "\r\n";
            }
          }
        } while (nFieldsLeft);
      }
    }
  }

  // If new log data is available, append to SD card
  if (sensorsRead == 0xFF) { // check if the there are newly read values for all the sensors
    digitalWrite(PANIC_LED, HIGH);
    if (DEBUG) {
      Serial.println(logHeader);
      logHeader = "";
    }
    saveSensorData();
    memset(validReads, 0, sizeof(validReads)); //set entries to zero
    sensorsRead = 0x00;
    for (uint8_t i = 0; i < N_KIT_SENS; i++) {
      bme[i].setTPH();
    }
    digitalWrite(PANIC_LED, LOW);
  }
}
