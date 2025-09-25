"""
LED_strip_controller.py
Drives a 12V LED strip with a smooth breathing effect as a reusable class,
reading parameters from config.json via config_manager.settings.
"""
import time
import math
import threading
import RPi.GPIO as GPIO
from config.config_manager import settings


class LEDBreather:
    """
    Controls a 12 V LED strip with a smooth breathing effect.

    Usage:
        breather = LED_Breather()
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
        self.pin = pin or settings.get("LED_strip_GPIO_pin", 32)
        self.pwm_freq = pwm_freq or settings.get("LED_strip_PWM_freq", 2500)
        self.period = breathe_period or settings.get("LED_strip_breath_period", 5.0)
        self.res = steps or settings.get("LED_strip_breath_res", 100)
        self.max_duty = max_duty or settings.get("LED_strip_max_duty_cycle", 100)
        
        # Precompute increments
        self.angle_step = 2 * math.pi / self.res
        self.delay = self.period / self.res

        # Thread control
        self._stop_event = threading.Event()
        self._thread = None

        # GPIO and PWM will be set up on start
        self._pwm = None

    def _setup_gpio(self):
        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)
        GPIO.setup(self.pin, GPIO.OUT)
        self._pwm = GPIO.PWM(self.pin, self.pwm_freq)
        self._pwm.start(0)

    def _cleanup(self):
        # Stop PWM and reset pins
        if self._pwm:
            self._pwm.ChangeDutyCycle(0)
            self._pwm.stop()
        # GPIO.cleanup()  # uncomment if you want to reset all GPIO pins

    def _run(self):
        """Internal run loop for breathing effect."""
        self._setup_gpio()
        angle = 0.0
        try:
            while not self._stop_event.is_set():
                # (1 - cos(angle)) / 2 scaled to max_duty
                duty = (1 - math.cos(angle)) * 50 * (self.max_duty / 100)
                self._pwm.ChangeDutyCycle(duty)

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


if __name__ == "__main__":
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