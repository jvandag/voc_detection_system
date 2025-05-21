#!/usr/bin/env python3
"""
cpu_temp_switch.py
Drives a GPIO pin HIGH if CPU temp ≥ threshold (from config.json), else LOW.
"""

import time
import subprocess
import RPi.GPIO as GPIO

from config_manager import settings

def get_cpu_temp():
    """Reads the CPU temperature in Celsius."""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            return int(f.readline()) / 1000.0
    except FileNotFoundError:
        output = subprocess.check_output(['vcgencmd', 'measure_temp']).decode()
        return float(output.split('=')[1].split("'")[0])

def main():
    # get settings from config file
    fan_pin     = settings.get("fan_GPIO_pin", 32)
    on_thresh   = settings.get("fan_on_temp_thresh", 0.0)
    off_thresh  = settings.get("fan_off_temp_thresh", None)
    poll_rate   = settings.get("fan_temp_poll_rate", 1)
    
    state = "OFF"

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(fan_pin, GPIO.OUT)

    try:
        while True:
            # Get the temperature of the cpu
            temp = get_cpu_temp()
            
            # toggle fan based off of temp
            if state == "ON" and off_thresh != None and (temp <= off_thresh):
                #GPIO.output(fan_pin, GPIO.LOW)
                state = "OFF"
            elif state == "OFF" and (temp >= on_thresh):
                #GPIO.output(fan_pin, GPIO.HIGH)
                state = "ON"
                
            print(f"CPU Temp: {temp:.2f}°C, Threshold Temp: {on_thresh:.1f}/{off_thresh:.1f}°C → Fan {state}")
            time.sleep(poll_rate)
    except KeyboardInterrupt:
        print("\nInterrupted; cleaning up...")
    finally:
        # Turn fan off
        GPIO.output(fan_pin, GPIO.LOW)
        # GPIO.cleanup()

if __name__ == "__main__":
    main()
