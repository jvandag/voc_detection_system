#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time

# Using PHYSICAL pin numbering here
PIN = 33  # physical pin 33 on the header

def main():
    # Use BOARD so "33" means physical pin 33
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)

    # Set pin as output and drive HIGH
    GPIO.setup(PIN, GPIO.OUT, initial=GPIO.HIGH)

    # Read back level from the same pin
    level = GPIO.input(PIN)
    print(f"Pin {PIN} (BOARD numbering) level after setup: {level} (1 = HIGH, 0 = LOW)")
    print("Pin should now be HIGH (~3.3V) on physical header pin 33.")
    print("Measure it with your multimeter. Press Ctrl+C to exit.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting and cleaning up...")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
