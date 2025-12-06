"""
LED_strip_controller.py
Drives a 12V LED strip with a smooth breathing effect as a reusable class,
reading parameters from config.json via config_manager.settings.

This version uses hardware PWM via the rpi-hardware-pwm library.

Assumptions:
- You are on a Raspberry Pi 4 running Ubuntu.
- /boot/firmware/config.txt (or /boot/config.txt) contains:
      dtoverlay=pwm,pin=13,func=4
  so that GPIO13 (header pin 33) is bound to PWM channel 1.
- /sys/class/pwm/pwmchip0 exists and permissions are set so this
  process can write to it (udev rule or sudo).
"""

import time
import math
import threading

from rpi_hardware_pwm import HardwarePWM

from ..config.config_manager import settings


class LEDBreather:
    """
    Controls a 12 V LED strip with a smooth breathing effect.

    Usage:
        breather = LEDBreather()
        breather.start()
        # do other work...
        breather.stop()
    """

    def __init__(self,
                 pin=None,
                 pwm_freq=None,
                 breathe_period=None,
                 steps=None,
                 max_duty=None):
        # Load settings with fallbacks
        # Note: pin is kept for configuration consistency, but the actual
        # hardware PWM routing is controlled by the dtoverlay and pwm_channel.
        self.pin = pin if pin is not None else settings.get("LED_strip_pin", 33)  # header pin 33 (BCM 13)
        self.pwm_freq = pwm_freq if pwm_freq is not None else settings.get("LED_strip_PWM_freq", 2500)
        self.period = breathe_period if breathe_period is not None else settings.get("LED_strip_breath_period", 5.0)
        self.res = steps if steps is not None else settings.get("LED_strip_breath_res", 100)
        self.max_duty = max_duty if max_duty is not None else settings.get("LED_strip_max_duty_cycle", 100)

        # GPIO13 (header pin 33) is PWM channel 1 when using dtoverlay=pwm,pin=13,func=4
        self.pwm_channel = 1

        # Precompute increments
        self.angle_step = 2 * math.pi / self.res
        self.delay = self.period / self.res

        # Thread control
        self._stop_event = threading.Event()
        self._thread = None

        # Hardware PWM handle (from rpi-hardware-pwm)
        self._pwm = None

    def _setup_pwm(self):
        """
        Set up hardware PWM using rpi-hardware-pwm.

        chip=0 corresponds to /sys/class/pwm/pwmchip0.
        """
        self._pwm = HardwarePWM(
            pwm_channel=self.pwm_channel,
            hz=self.pwm_freq,
            chip=0,
        )
        # Start at 0% duty cycle
        self._pwm.start(0.0)

    def _cleanup(self):
        """Stop hardware PWM and free the channel."""
        if self._pwm is not None:
            try:
                self._pwm.stop()
            finally:
                self._pwm = None

    def _run(self):
        """Internal run loop for breathing effect."""
        self._setup_pwm()
        angle = 0.0
        mult = 0.7
        epsilon = 1  # optional non-zero floor if you want to avoid fully off/on

        try:
            while not self._stop_event.is_set():
                # Compute duty in percent (0..max_duty*mult)
                duty = abs(math.cos(angle)) * self.max_duty * mult

                # Optional clamping to avoid exactly 0% or exactly max:
                # if duty < epsilon:
                #     duty = epsilon
                # elif duty > self.max_duty * mult - epsilon:
                #     duty = self.max_duty * mult - epsilon

                # rpi-hardware-pwm expects duty cycle as 0..100 (%)
                # We'll clamp just in case
                if duty < 0.0:
                    duty = 0.0
                if duty > 100.0:
                    duty = 100.0

                self._pwm.change_duty_cycle(duty)

                angle = (angle + self.angle_step) % (2 * math.pi)
                time.sleep(self.delay)
        finally:
            self._cleanup()

    def start(self):
        """Start the breathing effect in a background thread."""
        if self._thread and self._thread.is_alive():
            return  # already running
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Signal the breathing effect to stop and wait for cleanup."""
        self._stop_event.set()
        if self._thread:
            self._thread.join()


def main() -> int:
    breather = LEDBreather()
    try:
        print("Starting breathing effect. Press Ctrl+C to stop.")
        breather.start()
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        breather.stop()
    return 0


if __name__ == "__main__":
    exit(main())
