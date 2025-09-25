import RPi.GPIO as GPIO

class ShiftRegister:
    """
    Controls an N-bit shift register. Based on the SN74LV595A 8-bit shift register
    """
    def __init__(self,
                 num_bits: int = 8, # The number of bits "N" in the shift register
                 SER: int | None = None, # Serial input to the register
                 SRCLK: int | None = None, # Serial Clock, shifts in the current SER value
                 RCLK: int | None = None, # Saves the shifted in values to the output when asserted high
                 OE: int | None = None, # active low, when asserted it leaves the previous out values in the register
                          # until RCLK is asserted, otherwise outputs are low while shifting in
                 SRCLR: int | None = None, # active low, clears the shiftted in values when asserted
                 gpio_mode = GPIO.BCM): # outputs the value that was in the N-th bit when SRCLK is asserted
        
        self.num_bits = num_bits
        self.SER = SER
        self.SRCLK = SRCLK
        self.RCLK = RCLK
        self.SRCLR = SRCLR
        self.OE = OE
        
        self._initialize_gpio(gpio_mode)
        self.set_all_low()
    
    def wr_outputs(self, bit_nums: list):
        # sets the bits specified in the bit_nums list to high and every other bit to low

        if (self.OE != None): self._disable_shift_reg_outputs()
        GPIO.output(self.SRCLK, GPIO.LOW)
        GPIO.output(self.RCLK, GPIO.LOW)
        for i in range (self.num_bits):
            GPIO.output(self.SER, GPIO.HIGH if i in bit_nums else GPIO.LOW)
            GPIO.output(self.SRCLK, GPIO.HIGH)
            GPIO.output(self.SRCLK, GPIO.LOW)
        self._commit()
        if (self.OE != None): self._enable_shift_reg_outputs()

    def set_all_low(self):
        """Sets all shift register outputs to low"""
        if (self.SRCLR != None): 
            self._clear_shadow_registers()
            self._commit()
        else: self.wr_outputs(bit_nums=[]) # write nothing which will set all values low

    def _initialize_gpio(self):
        for pin in [self.SER, self.SRCLK, self.RCLK, self.SRCLR]:
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
        if self.OE != None:
            GPIO.setup(self.OE, GPIO.OUT, initial=GPIO.LOW)
    
    def _disable_shift_reg_outputs(self):
        # disable all shift register outputs
        try:
            if (self.OE == None): raise ValueError(f"OE pin not provided")
            GPIO.output(self.OE, GPIO.LOW)
        except ValueError as e:
            print(f"ERROR: {e}")
    
    def _enable_shift_reg_outputs(self):
        # enables shift reg outputs if they were disabled (enabled by default)
        try:
            if (self.OE == None): raise ValueError(f"OE pin not provided")
            GPIO.output(self.OE, GPIO.HIGH)
        except ValueError as e:
            print(f"ERROR: {e}")

    def _commit(self):
        # pushes values in shadow/storage registers to the output registers
        GPIO.output(self.RCLK, GPIO.LOW)
        GPIO.output(self.RCLK, GPIO.HIGH)
        GPIO.output(self.RCLK, GPIO.LOW)

    def _clear_shadow_registers(self):
        GPIO.output(self.SRCLR, GPIO.LOW)
        GPIO.output(self.SRCLR, GPIO.HIGH)
        GPIO.output(self.SRCLR, GPIO.LOW)
