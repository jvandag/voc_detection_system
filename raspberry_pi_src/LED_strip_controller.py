#!/usr/bin/env python3
"""
led_breath.py
Drives a 12 V LED strip with a smooth breathing effect, 
reading parameters from config.json via config.py.
"""

import time
import math
import RPi.GPIO as GPIO

from config_manager import settings

def main():
    # Pull settings (with fallbacks)
    pin            = settings.get("led_pin",       32)
    pwm_freq       = settings.get("pwm_freq",      100)    # Hz
    breathe_period = settings.get("breathe_period", 5.0)   # seconds
    steps          = settings.get("breath_steps",   100)   # resolution
    max_duty       = settings.get("max_LED_duty_cycle", 100)

    # Precompute timing and angle increment
    angle_step = 2 * math.pi / steps
    delay      = breathe_period / steps

    # GPIO setup
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)
    GPIO.setup(pin, GPIO.OUT)

    pwm = GPIO.PWM(pin, pwm_freq)
    pwm.start(0)

    try:
        angle = 0.0
        while True:
            # Cosine‐based duty cycle 0 -> max_duty_cycle -> 0
            duty = (1 - math.cos(angle)) * 50 * max_duty/100 # (1–cos)/2 * 100
            
            # update the duty cycle
            pwm.ChangeDutyCycle(duty)

            # update the cosine angle
            angle = (angle + angle_step) % (2 * math.pi)

            time.sleep(delay)

    except KeyboardInterrupt:
        print("\nStopping breathing effect…")

    finally:
        # Turn LED strip off
        pwm.ChangeDutyCycle(0)
        pwm.stop()
        # GPIO.cleanup()

if __name__ == "__main__":
    main()
