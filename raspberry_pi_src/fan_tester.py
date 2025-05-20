#!/usr/bin/env python3
"""
cpu_temp_pwm.py
Read Raspberry Pi CPU temperature and output PWM on a GPIO pin with duty cycle proportional to CPU temperature.

Usage:
    sudo python3 cpu_temp_pwm.py [GPIO_PIN]

Dependencies:
    RPi.GPIO
"""

import time
import sys
import RPi.GPIO as GPIO


def get_cpu_temp():
    """Reads the CPU temperature in Celsius."""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp_str = f.readline()
            return int(temp_str) / 1000.0
    except FileNotFoundError:
        # Fallback to vcgencmd if the sysfs path is unavailable
        import subprocess
        output = subprocess.check_output(['vcgencmd', 'measure_temp']).decode()
        # output format: "temp=45.8'C"
        return float(output.split('=')[1].split("'")[0])


def map_temp_to_duty(temp, min_temp=30.0, max_temp=80.0):
    """Maps temperature to a duty cycle between 0 and 100%."""
    if temp <= min_temp:
        return 0.0
    if temp >= max_temp:
        return 70.0
    # Linear mapping
    return (temp - min_temp) / (max_temp - min_temp) * 100.0


def main():
    # Default PWM GPIO pin (BCM numbering)
    pwm_pin = 32
    if len(sys.argv) > 1:
        try:
            pwm_pin = int(sys.argv[1])
        except ValueError:
            print("Invalid GPIO pin number provided. Falling back to pin 18.")

    # PWM frequency in Hertz
    pwm_freq = 1000

    # GPIO setup
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pwm_pin, GPIO.OUT)
    pwm = GPIO.PWM(pwm_pin, pwm_freq)
    pwm.start(0)  # Initialize with 0% duty cycle

    try:
        while True:
            temp = get_cpu_temp()
            duty = map_temp_to_duty(temp)
            pwm.ChangeDutyCycle(duty)
            print(f"CPU Temp: {temp:.2f} °C  ->  Duty Cycle: {duty:.1f}%")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user. Cleaning up...")
    finally:
        pwm.stop()
        GPIO.cleanup()


if __name__ == "__main__":
    main()
