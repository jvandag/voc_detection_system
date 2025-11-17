// AS7341 10 Channel Light Sensor https://www.adafruit.com/product/4698
// Example code
/* This example will read all channels from the AS7341 and print out reported values */

/* This example will read all channels from the AS7341 and print out reported values */

#include <Adafruit_AS7341.h>

Adafruit_AS7341 as7341;


void setup() {
  Serial.begin(115200);

  // Wait for communication with the host computer serial monitor
  while (!Serial) {
    delay(1);
  }
  
  if (!as7341.begin()){
    Serial.println("Could not find AS7341");
    while (1) { delay(10); }
  }

  as7341.setATIME(100);
  as7341.setASTEP(999);
  as7341.setGain(AS7341_GAIN_64X);
    // as7341.setGain(AS7341_GAIN_512X);
}

void loop() {
    // Print out the stored values for each channel
    Serial.println("0 mA LED");
    if (!as7341.readAllChannels()){
        Serial.println("Error reading all channels!");
        return;
    }
    Serial.print("F1 415nm/Violet   : ");
    Serial.println(as7341.getChannel(AS7341_CHANNEL_415nm_F1));
    Serial.print("F2 445nm/Indigo   : ");
    Serial.println(as7341.getChannel(AS7341_CHANNEL_445nm_F2));
    Serial.print("F3 480nm/Blue     : ");
    Serial.println(as7341.getChannel(AS7341_CHANNEL_480nm_F3));
    Serial.print("F4 515nm/Cyan     : ");
    Serial.println(as7341.getChannel(AS7341_CHANNEL_515nm_F4));
    Serial.print("F5 555nm/Green    : ");
    Serial.println(as7341.getChannel(AS7341_CHANNEL_555nm_F5));
    Serial.print("F6 590nm/Yellow   : ");
    Serial.println(as7341.getChannel(AS7341_CHANNEL_590nm_F6));
    Serial.print("F7 630nm/Orange   : ");
    Serial.println(as7341.getChannel(AS7341_CHANNEL_630nm_F7));
    Serial.print("F8 680nm/Red      : ");
    Serial.println(as7341.getChannel(AS7341_CHANNEL_680nm_F8));

    Serial.print("Clear/White?      : ");
    Serial.println(as7341.getChannel(AS7341_CHANNEL_CLEAR));

    Serial.print("Near Infrared     : ");
    Serial.println(as7341.getChannel(AS7341_CHANNEL_NIR));

    Serial.println("");

    Serial.println("25 mA LED blink");
    as7341.setLEDCurrent(25);
    as7341.enableLED(true);
    delay(50);
    if (!as7341.readAllChannels()){
        Serial.println("Error reading all channels!");
        return;
    }
    as7341.enableLED(false);
    delay(500);
    // Print out the stored values for each channel
    Serial.print("F1 415nm/Violet   : ");
    Serial.println(as7341.getChannel(AS7341_CHANNEL_415nm_F1));
    Serial.print("F2 445nm/Indigo   : ");
    Serial.println(as7341.getChannel(AS7341_CHANNEL_445nm_F2));
    Serial.print("F3 480nm/Blue     : ");
    Serial.println(as7341.getChannel(AS7341_CHANNEL_480nm_F3));
    Serial.print("F4 515nm/Cyan     : ");
    Serial.println(as7341.getChannel(AS7341_CHANNEL_515nm_F4));
    Serial.print("F5 555nm/Green    : ");
    Serial.println(as7341.getChannel(AS7341_CHANNEL_555nm_F5));
    Serial.print("F6 590nm/Yellow   : ");
    Serial.println(as7341.getChannel(AS7341_CHANNEL_590nm_F6));
    Serial.print("F7 630nm/Orange   : ");
    Serial.println(as7341.getChannel(AS7341_CHANNEL_630nm_F7));
    Serial.print("F8 680nm/Red      : ");
    Serial.println(as7341.getChannel(AS7341_CHANNEL_680nm_F8));

    Serial.print("Clear/White?      : ");
    Serial.println(as7341.getChannel(AS7341_CHANNEL_CLEAR));

    Serial.print("Near Infrared     : ");
    Serial.println(as7341.getChannel(AS7341_CHANNEL_NIR));

    Serial.println("");
}