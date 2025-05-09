from queue import Queue

DEBUG = True

class EnvironmentalChamber:
    def __init__(
        self, 
        name: str, 
        gas_valve_pin: int,
        vac_valve_pin: int
    ):
        
        self.name = name
        self.gas_valve_pin = gas_valve_pin
        self.vac_valve_pin = vac_valve_pin
        self.status = "normal"

        
class CtrlSystem:
    def __init__(self, vacuum_ctrl_pin: int):
        self.chambers: dict[str, EnvironmentalChamber] = {}
        
        # The queue for chambers that need to be flushed with gas
        # Only one chamber's gas valve should be open at a time
        self.gas_queue = Queue()
        
        # A list containing all of the pins assigned to gas valves
        self.gas_pins = []
        
        # The queue for chambers that need to be vacuumed
        # Only one chamber's vacuum valve should be open at a time
        self.vacuum_queue = Queue()
        
        # a list containing all of the pins assigned to vacuum valves
        self.vacuum_pins = []
        
        # The pin that controls power to the vacuum pump
        self.vacuum_ctrl_pin = vacuum_ctrl_pin
    
    def turn_sys_on():
        pass
     
    def shut_sys_down(self):
        '''Kills all threads, closes all valves, and turns off the vacuum pump by setting all GPIO pins to LOW'''
        self.reset_all_pins()
     
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
            self.gas_pins.append(gas_valve_pin)
            self.vacuum_pins.append(vac_valve_pin)
            return True
    
    def turn_vacuum_on(self):
        """Turns power to the vacuum pump on by setting its GPIO pin HIGH"""
        self.set_pin_high(self.vacuum_ctrl_pin)
        if (DEBUG): print("Vacuum turned ON")
    
    def turn_vacuum_off(self):
        """Turns power to the vacuum pump off by setting its GPIO pin LOW"""
        self.set_pin_low(self.vacuum_ctrl_pin)
        if (DEBUG): print("Vacuum turned OFF")
       
    def open_gas_valve(self, pin_num):
        """Opens the gas valve if the pin has been declared as a gas valve control pin"""
        if (pin_num not in self.gas_pins):
            self.shut_sys_down()
            raise KeyError(f"Tried to set {pin_num} HIGH but pin is not specified as a gas pin")
        else:
            self.set_pin_high(pin_num)
    
    def close_gas_valve(self, pin_num):
        """Closes the gas valve if the pin has been declared as a gas valve control pin"""
        if (pin_num not in self.gas_pins):
            self.shut_sys_down()
            raise KeyError(f"Tried to set {pin_num} LOW but pin is not specified as a gas pin")
        else:
            self.set_pin_low(pin_num)
    
    def open_vacuum_valve(self):
        pass
    
    def set_pin_high(self, pin_num):
        """Sets the GPIO pin HIGH"""
        # ADD CODE TO CHANGE GPIO ON RP4 HERE
        if (DEBUG): print(f"Pin {pin_num} set HIGH")
    
    def set_pin_low(self, pin_num):
        """Sets the GPIO pin LOW"""
        # ADD CODE TO CHANGE GPIO ON RP4 HERE
        if (DEBUG): print(f"Pin {pin_num} set LOW")
    
    def toggle_pin(self, pin_num):
        """Toggles the logic level of the GPIO pin"""
        # ADD CODE TO CHANGE GPIO ON RP4 HERE
        if (DEBUG): print(f"Pin {pin_num} toggled")
        
    def reset_all_pins(self):
        '''Sets all GPIO pins on the board to LOW'''
        # ADD CODE TO CHANGE GPIO ON RP4 HERE