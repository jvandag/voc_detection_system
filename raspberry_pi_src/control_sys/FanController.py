"""
fan_controller.py

Class-based CPU temperature fan controller for Raspberry Pi.
Reads CPU temperature and switches a GPIO pin HIGH when temperature >= on-threshold,
and LOW when temperature <= off-threshold. Configurable via config_manager settings
or via constructor parameters.
"""

import time
import subprocess
import RPi.GPIO as GPIO

from config.config_manager import settings


def get_cpu_temp():
    """Reads the CPU temperature in Celsius."""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            return int(f.readline()) / 1000.0
    except FileNotFoundError:
        output = subprocess.check_output(['vcgencmd', 'measure_temp']).decode()
        return float(output.split('=')[1].split("'")[0])


class FanController:
    """
    Class to control a GPIO pin based on CPU temperature thresholds.

    Parameters:
        fan_pin (int): GPIO pin number (BOARD mode) for fan control.
        on_thresh (float): Temperature (°C) to turn fan on.
        off_thresh (float): Temperature (°C) to turn fan off.
        poll_rate (float): Seconds between temperature checks.
        gpio_mode: GPIO numbering mode (GPIO.BOARD or GPIO.BCM).
    """
    def __init__(self,
                 fan_pin=None,
                 on_thresh=None,
                 off_thresh=None,
                 poll_rate=None,
                 gpio_mode=GPIO.BCM):
        # Load defaults from config if not provided
        self.fan_pin = fan_pin if fan_pin is not None else settings.get("fan_pin", 32)
        self.on_thresh = on_thresh if on_thresh is not None else settings.get("fan_on_temp_thresh", 0.0)
        self.off_thresh = off_thresh if off_thresh is not None else settings.get("fan_off_temp_thresh", None)
        self.poll_rate = poll_rate if poll_rate is not None else settings.get("fan_temp_poll_rate", 1)

        # Internal state: False=OFF, True=ON
        self.state = False

        # GPIO setup
        GPIO.setwarnings(False)
        GPIO.setmode(gpio_mode)
        GPIO.setup(self.fan_pin, GPIO.OUT)
        GPIO.output(self.fan_pin, GPIO.LOW)

    def update(self):
        """
        Check CPU temperature and update fan state.
        Returns:
            temp (float): current CPU temperature
            state (bool): True if fan ON, False if OFF
        """
        temp = get_cpu_temp()
        if self.state and self.off_thresh is not None and temp <= self.off_thresh:
            GPIO.output(self.fan_pin, GPIO.LOW)
            self.state = False
        elif not self.state and temp >= self.on_thresh:
            GPIO.output(self.fan_pin, GPIO.HIGH)
            self.state = True
        return temp, self.state

    def run(self, use_thresh=True):
        """
        Start the polling loop. Loop until stopped externally.
        """
        if use_thresh:
            while True:
                temp, state = self.update()
                off = self.off_thresh if self.off_thresh is not None else self.on_thresh
                print(f"CPU Temp: {temp:.2f}°C, thresholds on={self.on_thresh:.1f}, off={off:.1f} -> Fan {'ON' if state else 'OFF'}")
                time.sleep(self.poll_rate)
        else:
            GPIO.output(self.fan_pin, GPIO.HIGH)

    def stop(self):
        """
        Stop the controller: turn fan off and clean up GPIO.
        """
        GPIO.output(self.fan_pin, GPIO.LOW)
        # GPIO.cleanup() uncomment if you want all gpio pins to be cleared
        print("Fan controller stopped and GPIO cleaned up.")


if __name__ == "__main__":
    controller = FanController()
    try:
        controller.run()
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Stopping controller...")
    finally:
        controller.stop()