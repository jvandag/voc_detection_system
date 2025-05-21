# mux16.py
"""
MUX16 — 4-to-16 bidirectional GPIO multiplexer controller

Usage:
    from mux16 import MUX16

    # BCM-numbered GPIO pins for S0…S3, and the shared SIG line:
    sel_pins = [17, 27, 22, 23]
    sig_pin  = 24

    mux = MUX16(select_pins=sel_pins, signal_pin=sig_pin, gpio_mode=GPIO.BCM)
    try:
        # Drive channel 5 high:
        mux.write(5, GPIO.HIGH)

        # Read from channel 12:
        val = mux.read(12)
        print("Channel 12 reads", val)

    finally:
        mux.cleanup()
"""

import RPi.GPIO as GPIO
import time

class MUX16:
    def __init__(self, select_pins: list[int], signal_pin: int, gpio_mode = GPIO.BCM, 
                 initial_channel: int = 0, settle_time: float = 0.001):
        """
        Helper class for controlling a MUX with 4 select lines, 1 in out signal line,
        and 16 channels
        
        Parameters
        --------------------
            select_pins:
                `list[int]` of 4 GPIO pins [S0, S1, S2, S3]
            signal_pin:
                single GPIO pin (`int`) for the shared signal line
            gpio_mode:
                GPIO.BCM or GPIO.BOARD
            initial_channel:
                channel (0–15) (`int`) to select at init
            settle_time:
                delay in seconds (`int`) after switching before read/write
        """
        
        if len(select_pins) != 4:
            raise ValueError("select_pins must be a list of 4 pins")
        self.sel = select_pins
        self.sig = signal_pin
        self.settle = settle_time

        GPIO.setmode(gpio_mode)
        GPIO.setwarnings(False)

        # Setup select pins as outputs
        for pin in self.sel:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)

        # We'll configure signal pin direction on the fly
        self.channel = None
        self.select(initial_channel)

    def select(self, channel):
        """Set the 4-bit select lines to choose channel 0–15.
        Note: when a channel is selected the previous channel will stop being driven,
        inputs are not latched.
        """
        
        if not (0 <= channel < 16):
            raise ValueError("channel must be between 0 and 15")
        # Write bits S0..S3
        for bit in range(4):
            GPIO.output(self.sel[bit], GPIO.HIGH if (channel >> bit) & 1 else GPIO.LOW)
        self.channel = channel
        time.sleep(self.settle)

    def write(self, channel, value):
        """
        Drive the selected channel pin high or low.
        value: GPIO.HIGH or GPIO.LOW (or 1/0)
        """
        self.select(channel)
        GPIO.setup(self.sig, GPIO.OUT)
        GPIO.output(self.sig, value)

    def read(self, channel):
        """
        Read the level on the selected channel pin.
        Returns: GPIO.HIGH (1) or GPIO.LOW (0)
        """
        self.select(channel)
        GPIO.setup(self.sig, GPIO.IN)
        return GPIO.input(self.sig)

    def cleanup(self):
        """Reset all used GPIOs."""
        GPIO.cleanup(self.sel + [self.sig])


if __name__ == "__main__":
    # BCM-numbered GPIO pins for S0…S3, and the shared SIG line:
    sel_pins = [17, 27, 22, 23]
    sig_pin  = 24

    mux = MUX16(select_pins=sel_pins, signal_pin=sig_pin, gpio_mode=GPIO.BCM)
    try:
        # Drive channel 5 high:
        mux.write(5, GPIO.HIGH)

        # Read from channel 12:
        val = mux.read(12)
        print("Channel 12 reads", val)

    finally:
        mux.cleanup()
