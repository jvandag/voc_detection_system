from queue import Queue
import RPi.GPIO as GPIO
from dotenv import dotenv_values

config = dotenv_values(".env")

from EnvironmentalChamber import EnvironmentalChamber

class ControlSystem:
    def __init__(self, vacuum_ctrl_pin: int, ambient_valve_pin: int = None):
        GPIO.setmode(GPIO.BOARD)
        
        self.chambers: dict[str, EnvironmentalChamber] = {}
        
        # The queue for chambers that need to be flushed with gas
        # Only one chamber's gas valve should be open at a time
        self.gas_queue = Queue()
        
        # A list containing all of the pins assigned to gas valves
        self.gas_pins = []
        
        # The queue for chambers that need to be vacuumed
        # Only one chamber's vacuum valve should be open at a time
        self.vacuum_queue = Queue()
        
        # A list containing all of the pins assigned to vacuum valves
        self.vacuum_pins = []
        
        # The pin that controls power to the vacuum pump
        self.vacuum_ctrl_pin = vacuum_ctrl_pin
        self.ambient_valve_pin: int | None = ambient_valve_pin
        
        GPIO.setup(vacuum_ctrl_pin, GPIO.OUT, initial=GPIO.LOW)
        
        if ambient_valve_pin != None:
            GPIO.setup(ambient_valve_pin, GPIO.OUT, initial=GPIO.LOW)
    
    def turn_sys_on():
        pass
     
    def shut_sys_down(self):
        '''Kills all threads, closes all valves, and turns off the vacuum pump by setting all GPIO pins to LOW'''
        self.reset_all_pins()
        GPIO.cleanup()
     
    def add_chamber(self, name: str, gas_valve_pin: int, vac_valve_pin: int) -> bool:
        """Initializes a chamber and adds it to the list of chambers for the system to control

        Parameters
        ---------
            name: `str`
                The name of the chamber
            gas_valve_pin: `int`
                The GPIO pin num used to open and close the gas valve
            vac_valve_pin: `int`
                The GPIO pin num used to open and close the vacuum valve

        Returns
        ---------
            `bool`
                `True` if the chamber was successfully added
        """
        if name in self.chambers:
            raise KeyError(f"Tried to add chamber with name \"{name}\" when an existing chamber with that name already exists")
        else:
            self.chambers[name] = EnvironmentalChamber(name=name, gas_valve_pin=gas_valve_pin, vac_valve_pin=vac_valve_pin)
            GPIO.setup([gas_valve_pin, vac_valve_pin], GPIO.OUT, initial=GPIO.LOW)
            self.gas_pins.append(gas_valve_pin)
            self.vacuum_pins.append(vac_valve_pin)
            return True
        
    
    def disable_chamber(self, chamber: EnvironmentalChamber, new_status: str):
        self.set_pin_low(chamber.gas_valve_pin)
        self.set_pin_low(chamber.vac_valve_pin)
        chamber.status = new_status # ERROR or DISABLED by convention
    
    def queue_gas_valve(self, chamber):
        """Adds a gas valve to the queue for being opened so that no two gas valves will be opened at the same time"""
    
    def queue_vacuum_valve(self, chamber):
        """Adds a vacuum valve to the queue for being opened so that no two vacuum valves will be opened at the same time"""
    
    def turn_vacuum_on(self):
        """Turns power to the vacuum pump on by setting its GPIO pin HIGH"""
        self.set_pin_high(self.vacuum_ctrl_pin)
        if (config.DEBUG): print("Vacuum turned ON")
    
    def turn_vacuum_off(self):
        """Turns power to the vacuum pump off by setting its GPIO pin LOW"""
        self.set_pin_low(self.vacuum_ctrl_pin)
        if (config.DEBUG): print("Vacuum turned OFF")
    
    def open_gas_valve(self, chamber: EnvironmentalChamber):
        """Opens the gas valve for the chamber"""
        try:  
            if (chamber.gas_valve_pin not in self.gas_pins):
                raise Exception(f"Tried to set {chamber.gas_valve_pin} HIGH but pin is not initialized as a gas pin")
            elif (GPIO.input(chamber.vac_valve_pin) and not chamber.allow_multi_valves):
                raise Exception(f"Tried to set gas_valve pin {chamber.gas_valve_pin} to HIGH but vacuum valve is open")
            else:
                self.set_pin_high(chamber.gas_valve_pin)
        except:
            self.disable_chamber(chamber=chamber, new_status="ERROR")
            
    
    def close_gas_valve(self, chamber: EnvironmentalChamber):
        """Closes the gas valve of the chamber"""
        try:
            if (chamber.gas_valve_pin not in self.gas_pins):
                raise Exception(f"Tried to set {chamber.gas_valve_pin} LOW but pin is not initialized as a gas pin")
            else:
                self.set_pin_low(chamber.gas_valve_pin)
        except: 
            self.disable_chamber(chamber=chamber, new_status="ERROR")
    
    def open_vacuum_valve(self, chamber: EnvironmentalChamber):
        """Opens the vacuum valve of the chamber"""
        try:  
            if (chamber.vac_valve_pin not in self.vacuum_pins):
                raise Exception(f"Tried to set {chamber.vac_valve_pin} HIGH but pin is not initialized as a gas pin")
            elif (GPIO.input(chamber.gas_valve_pin) and not chamber.allow_multi_valves):
                raise Exception(f"Tried to set gas_valve pin {chamber.vac_valve_pin} to HIGH but vacuum valve is open")
            else:
                self.set_pin_high(chamber.vac_valve_pin)
        except:
            self.disable_chamber(chamber=chamber, new_status="ERROR")
            
            
    def close_vacuum_valve(self, chamber: EnvironmentalChamber):
        """Closes the vacuum valve of the chamber"""
        try:
            if (chamber.vac_valve_pin not in self.gas_pins):
                raise Exception(f"Tried to set {chamber.vac_valve_pin} LOW but pin is not initialized as a gas pin")
            else:
                self.set_pin_low(chamber.vac_valve_pin)
        except: 
            self.disable_chamber(chamber=chamber, new_status="ERROR")
    
    def set_pin_high(self, pin):
        """Sets the GPIO pin HIGH"""
        GPIO.output(pin, GPIO.HIGH)
        if (config.DEBUG): print(f"Pin {pin} set HIGH")
    
    def set_pin_low(self, pin):
        """Sets the GPIO pin LOW"""
        GPIO.output(pin, GPIO.LOW)
        if (config.DEBUG): print(f"Pin {pin} set LOW")
        
    def toggle_pin(self, pin):
        """Toggles the logic level of the GPIO pin"""
        GPIO.output(pin, not GPIO.input(pin))
        if (config.DEBUG): print(f"Pin {pin} toggled")
        
    def reset_all_pins(self):
        '''Sets all GPIO pins on the board to LOW'''
        for pin in [*self.gas_pins, *self.vacuum_pins, self.vacuum_ctrl_pin]:
            GPIO.output(pin, GPIO.LOW)
            
        if (self.ambient_valve_pin != None):
            GPIO.output(self.ambient_valve_pin, GPIO.LOW)