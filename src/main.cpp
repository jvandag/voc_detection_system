#include <Arduino.h>
#include <SD.h>
#include "bme68xLibrary.h"
#include "commMux\commMux.h"
#include <Esp.h>

#include "feather_v2_config.h" // must be after other includes as it overwrides certain pins and values


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
    DEBUG_PRINT("Creating new log file: " + logFile);
    file = SD.open(logFile, FILE_WRITE); //open in write to create a new file
    //file.close(); //the file isn't created on the SD card until it's closed
    String exists = SD.exists(logFile) ? "yes" : "no";
    DEBUG_PRINT("file exists?: " + exists);
  }
  else { //if path file exists append to it rather than write over
    DEBUG_PRINT("Opening existing log file: " + logFile);
    file = SD.open(logFile, FILE_APPEND); 
  }
  if (!file) {
    DEBUG_PRINT("Failed to open file for appending: " + logFile);
    panicLeds();
  }
  String data = SAMPLE_NAME;
  for (int i = 0; i < 8; i++) {
    data += String(",") + String(i) + "," + String(validReads[i]);
  }
  if (file.println(data)) {
    DEBUG_PRINT("Wrote to " + logFile);
  } else {
    DEBUG_PRINT("Write append failed");
  }
  file.close();
}

/*!
 * @brief Configures and initializes hardware and sensors
 */
void setup(void) {
  #if DEBUG
    Serial.begin(9600);
  #endif
  delay(5000);  // Give time for Serial Monitor to connect
  DEBUG_PRINT("\nInitializing Setup!");
  //yield();
  /* Initiate SPI communication (shared bus for sensor multiplexer) */
  SPI.begin(SCK, MISO, MOSI, CS);
  Wire.begin(SDA, SCL, I2C_FREQ);
  //Wire.setTimeout(100);           // give it a finite ACK timeout (ms)
  commMuxBegin(Wire, SPI);
  DEBUG_PRINT("CommMux Began...");
  pinMode(PANIC_LED, OUTPUT);
  delay(100);

  /* Setting up SD Card */
  DEBUG_PRINT("Initializing SD card...");

  if (!SD.begin(SD_PIN_CS)) {
    DEBUG_PRINT("SD Card not found or initialization failed");
    panicLeds();
  } 
  else {
    DEBUG_PRINT("SD Card found");
  }

  /* Communication interface set for all the 8 sensors in the development kit */
  for (uint8_t i = 0; i < N_KIT_SENS; i++) {
    commSetup[i] = commMuxSetConfig(Wire, SPI, i, commSetup[i]);
    bme[i].begin(BME68X_SPI_INTF, commMuxRead, commMuxWrite, commMuxDelay, &commSetup[i]);
    if (bme[i].checkStatus()) {
      DEBUG_PRINT("Initializing sensor " + String(i) + " failed with error " + bme[i].statusString());
      panicLeds();
    }
  }
    setSensorHeaters();
    logHeader = "";
    logFile = getLogFileName();
    DEBUG_PRINT("Path: " + logFile);
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
              DEBUG_PRINT("Skip I:" + String(i) +
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
