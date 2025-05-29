# mux.py
"""
MUX — N-to-2^N bidirectional GPIO multiplexer controller

Usage:
    from mux import MUX

    # BCM-numbered GPIO pins for select lines [S0…S(N-1)] and the shared SIG line:
    sel_pins = [17, 27, 22]   # e.g. 3 select pins → 8 channels
    sig_pin  = 24

    mux = MUX(select_pins=sel_pins, signal_pin=sig_pin, gpio_mode=GPIO.BCM)
    try:
        # Drive channel 5 high:
        mux.write(5, GPIO.HIGH)

        # Read from channel 2:
        val = mux.read(2)
        print("Channel 2 reads", val)

    finally:
        mux.cleanup()
"""

import RPi.GPIO as GPIO
import time

class MUX:
    def __init__(self,
                 select_pins: list[int],
                 signal_pin: int,
                 gpio_mode=GPIO.BCM,
                 initial_channel: int = 0,
                 settle_time: float = 0.001):
        """
        Generic multiplexer controller:
        - N select lines -> 2^N channels
        - 1 shared signal line (bidirectional)

        Parameters
        ----------
        select_pins : list[int]
            GPIO pins for select bits [S0, S1, ..., S(N-1)]
        signal_pin : int
            Shared data pin (input or output)
        gpio_mode : GPIO.BCM or GPIO.BOARD
        initial_channel : int
            Channel (0 to 2^N - 1) to select at init
        settle_time : float
            Delay (s) after switching before read/write
        """
        self.sel = select_pins
        self.sig = signal_pin
        self.settle = settle_time
        self.n_bits = len(self.sel)
        self.max_channel = 1 << self.n_bits

        if self.n_bits < 1:
            raise ValueError("Must have at least one select pin")

        GPIO.setmode(gpio_mode)
        GPIO.setwarnings(False)

        # Initialize select lines
        for pin in self.sel:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)

        self.channel = None
        self.select(initial_channel)

    def select(self, channel: int):
        """
        Set select lines to choose the given channel.
        """
        if not (0 <= channel < self.max_channel):
            raise ValueError(
                f"channel must be between 0 and {self.max_channel - 1}")

        for bit in range(self.n_bits):
            level = GPIO.HIGH if ((channel >> bit) & 1) else GPIO.LOW
            GPIO.output(self.sel[bit], level)

        self.channel = channel
        time.sleep(self.settle)

    def write(self, channel: int, value: int):
        """
        Drive the selected channel pin high or low.
        """
        self.select(channel)
        GPIO.setup(self.sig, GPIO.OUT)
        GPIO.output(self.sig, value)

    def read(self, channel: int) -> int:
        """
        Read the level on the selected channel pin.
        Returns GPIO.HIGH (1) or GPIO.LOW (0).
        """
        self.select(channel)
        GPIO.setup(self.sig, GPIO.IN)
        return GPIO.input(self.sig)

    def cleanup(self):
        """
        Reset all used GPIOs.
        """
        GPIO.cleanup(self.sel + [self.sig])


if __name__ == "__main__":
    # Example for 8-channel MUX:
    sel_pins = [17, 27, 22]  # 3 select lines → 8 channels
    sig_pin = 24

    mux = MUX(select_pins=sel_pins, signal_pin=sig_pin, gpio_mode=GPIO.BCM)
    try:
        mux.write(3, GPIO.HIGH)
        val = mux.read(5)
        print("Channel 5:", "HIGH" if val else "LOW")

    finally:
        mux.cleanup()
