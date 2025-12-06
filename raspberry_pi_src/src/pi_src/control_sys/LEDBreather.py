"""
LED_strip_controller.py
Drives a 12V LED strip with a smooth breathing effect as a reusable class,
reading parameters from config.json via config_manager.settings.

This version uses pigpio hardware PWM, so it stays smooth even under CPU load.

Notes:
- 'pin' is a BCM GPIO number (NOT the header pin number).
- Use a hardware-PWM-capable pin, e.g. GPIO13 (header pin 33) or GPIO18.
"""

import time
import math
import threading
import pigpio

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
        # IMPORTANT: LED_strip_pin must be a BCM GPIO number that supports HW PWM
        # (e.g. 13 or 18). The default here is 13.
        self.pin = pin if pin is not None else settings.get("LED_strip_pin", 13)

        self.pwm_freq = pwm_freq if pwm_freq is not None else settings.get("LED_strip_PWM_freq", 2500)
        self.period = breathe_period if breathe_period is not None else settings.get("LED_strip_breath_period", 5.0)
        self.res = steps if steps is not None else settings.get("LED_strip_breath_res", 100)
        self.max_duty = max_duty if max_duty is not None else settings.get("LED_strip_max_duty_cycle", 100)

        # Precompute increments for breathing shape
        self.angle_step = 2 * math.pi / self.res
        self.delay = self.period / self.res

        # Thread control
        self._stop_event = threading.Event()
        self._thread = None

        # pigpio handle
        self._pi = pigpio.pi()  # connects to local pigpiod
        if not self._pi.connected:
            raise RuntimeError(
                "Cannot connect to pigpio daemon. "
                "Is pigpiod running? (try: sudo systemctl start pigpiod)"
            )

    def _setup_pwm(self):
        """
        Configure hardware PWM on the selected pin.

        pigpio will automatically select the proper ALT function for HW PWM
        on a supported pin (e.g. 13, 18).
        """
        # Ensure pin is set as output (pigpio will also handle mode on hardware_PWM)
        self._pi.set_mode(self.pin, pigpio.OUTPUT)
        # Start with 0% duty (duty argument is 0..1_000_000)
        self._pi.hardware_PWM(self.pin, self.pwm_freq, 0)

    def _cleanup(self):
        """
        Stop PWM on this pin.

        hardware_PWM(pin, 0, 0) disables PWM.
        """
        try:
            self._pi.hardware_PWM(self.pin, 0, 0)
        except pigpio.error:
            # Ignore errors during cleanup
            pass

    def _run(self):
        """Internal run loop for breathing effect."""
        self._setup_pwm()
        angle = 0.0
        mult = 0.85
        epsilon = 1  # optional non-zero floor if you want to avoid fully off/on

        try:
            while not self._stop_event.is_set():
                # Breathing shape: |cos(angle)| scaled to max_duty * mult
                duty_percent = abs(math.cos(angle)) * self.max_duty * mult

                # Optional clamping to avoid fully off / full on
                # if duty_percent < epsilon:
                #     duty_percent = epsilon
                # elif duty_percent > self.max_duty * mult - epsilon:
                #     duty_percent = self.max_duty * mult - epsilon

                # Clamp to [0, 100] just in case
                if duty_percent < 0.0:
                    duty_percent = 0.0
                if duty_percent > 100.0:
                    duty_percent = 100.0

                # Map 0–100 % -> 0–1_000_000 for pigpio.hardware_PWM
                duty_hw = int(duty_percent / 100.0 * 1_000_000)
                self._pi.hardware_PWM(self.pin, self.pwm_freq, duty_hw)

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
        # Optionally close pigpio connection if this class "owns" it
        if self._pi is not None:
            self._pi.stop()
            self._pi = None


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
