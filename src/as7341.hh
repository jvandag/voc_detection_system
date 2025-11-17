// AS7341 10 Channel Light Sensor https://www.adafruit.com/product/4698
// Example code
/* This example will read all channels from the AS7341 and print out reported values */

/* This example will read all channels from the AS7341 and print out reported values */

#include "feather_v2_config.hh"
#include <Adafruit_AS7341.h>

Adafruit_AS7341 as7341;


void as7341_init() {
  if (!as7341.begin()){
    Serial.print("##ALERT, Could not find AS7341 during init for chamber " + String(CHAMBER_NAME));
    
  }
  as7341.setATIME(100);
  as7341.setASTEP(999);
  as7341.setGain(AS7341_GAIN_64X);
}

bool as7341_read_sensor(int (&read_arr)[10]) {
    DEBUG_PRINT("25 mA LED blink");
    as7341.setLEDCurrent(25);
    as7341.enableLED(true);
    delay(10);
    if (!as7341.readAllChannels()){
        Serial.print("##ALERT, Failed to call readAllChannels as7341 for chamber " + String(CHAMBER_NAME));
        return false;
    }
    as7341.enableLED(false);
    
    read_arr[0] = as7341.getChannel(AS7341_CHANNEL_415nm_F1);
    read_arr[1] = as7341.getChannel(AS7341_CHANNEL_445nm_F2);
    read_arr[2] = as7341.getChannel(AS7341_CHANNEL_480nm_F3);
    read_arr[3] = as7341.getChannel(AS7341_CHANNEL_515nm_F4);
    read_arr[4] = as7341.getChannel(AS7341_CHANNEL_555nm_F5);
    read_arr[5] = as7341.getChannel(AS7341_CHANNEL_590nm_F6);
    read_arr[6] = as7341.getChannel(AS7341_CHANNEL_630nm_F7);
    read_arr[7] = as7341.getChannel(AS7341_CHANNEL_680nm_F8);
    read_arr[8] = as7341.getChannel(AS7341_CHANNEL_CLEAR);
    read_arr[9] = as7341.getChannel(AS7341_CHANNEL_NIR);

    #ifdef DEBUG
        // Print out the stored values for each channel
        // Serial.print("F1 415nm/Violet   : ");
        // Serial.println(as7341.getChannel(AS7341_CHANNEL_415nm_F1));
        // Serial.print("F2 445nm/Indigo   : ");
        // Serial.println(as7341.getChannel(AS7341_CHANNEL_445nm_F2));
        // Serial.print("F3 480nm/Blue     : ");
        // Serial.println(as7341.getChannel(AS7341_CHANNEL_480nm_F3));
        // Serial.print("F4 515nm/Cyan     : ");
        // Serial.println(as7341.getChannel(AS7341_CHANNEL_515nm_F4));
        // Serial.print("F5 555nm/Green    : ");
        // Serial.println(as7341.getChannel(AS7341_CHANNEL_555nm_F5));
        // Serial.print("F6 590nm/Yellow   : ");
        // Serial.println(as7341.getChannel(AS7341_CHANNEL_590nm_F6));
        // Serial.print("F7 630nm/Orange   : ");
        // Serial.println(as7341.getChannel(AS7341_CHANNEL_630nm_F7));
        // Serial.print("F8 680nm/Red      : ");
        // Serial.println(as7341.getChannel(AS7341_CHANNEL_680nm_F8));

        // Serial.print("Clear/White?      : ");
        // Serial.println(as7341.getChannel(AS7341_CHANNEL_CLEAR));

        // Serial.print("Near Infrared     : ");
        // Serial.println(as7341.getChannel(AS7341_CHANNEL_NIR));

        // Serial.println("");
    #endif //DEBUG
    return true;
}

bool as7341_averaged_read(int (&read_arr)[10], int num_reads = 3) {
    int avg_arr[10] = {0};
    for (int i = 0; i < num_reads; i++) {
        int read[10] = {0};
        if (as7341_read_sensor(read)) {
            for (int channel = 0; channel < 10; channel++) {
                avg_arr[channel] += read[channel];
            }
            delay(25);
        }
        else {
            Serial.print("##ALERT, Failed to call averaged_read as7341 for "  + String(CHAMBER_NAME));
            return false;
        }
    }
    for (int channel = 0; channel < 10; channel++) {
        read_arr[channel] = avg_arr[channel] / num_reads;
    }
    return true;
}