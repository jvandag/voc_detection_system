#include <Arduino.h>

#include <Esp.h>

void setup() {
    Serial.begin(9600);
    pinMode(LED_BUILTIN, OUTPUT);
  }
  
  void loop() {
    digitalWrite(LED_BUILTIN, HIGH);
    Serial.println("High!");
    delay(2000);
    digitalWrite(LED_BUILTIN, LOW);
    delay(500);

    digitalWrite(LED_BUILTIN, HIGH);
    Serial.println("High!");
    delay(500);
    digitalWrite(LED_BUILTIN, LOW);
    delay(100);

    digitalWrite(LED_BUILTIN, HIGH);
    Serial.println("High!");
    delay(500);
    digitalWrite(LED_BUILTIN, LOW);
    delay(100);
  }
  