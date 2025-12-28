from queue import Queue
import time
import RPi.GPIO as GPIO
from .SerialMonitor import SerialMonitor
from .LEDBreather import LEDBreather
from .FanController import FanController
from ..config.config_manager import settings, save_settings
from .DiscordAlerts import send_discord_alert_webhook
from .ShiftRegister import ShiftRegister
from .EnvironmentalChamber import EnvironmentalChamber

class ControlSystem:
    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        self.chambers: dict[str, EnvironmentalChamber] = {}
        # The queue for chamber groups that need to be purged (vacuum and flushed with gas)
        self.purge_queue = Queue()

        self.groups = settings.get("chamber_groups", {})
        
        # The pin that controls power to the vacuum pump
        self.vacuum_ctrl_pin = settings.get("vacuum_ctrl_pin", -1)

        self.ambient_valve_pin = settings.get("ambient_valve_pin", None) # Unutlized
        if self.ambient_valve_pin == -1: self.ambient_valve_pin = None
        

        self.valve_shift_reg = ShiftRegister(num_bits=16)

        GPIO.setup(self.vacuum_ctrl_pin, GPIO.OUT, initial=GPIO.LOW)
        if self.ambient_valve_pin != None:
            GPIO.setup(self.ambient_valve_pin, GPIO.OUT, initial=GPIO.LOW)

        if (settings.get("DEBUG", False)): 
            print("Turning serial monitor on")
        self.serial_monitor = SerialMonitor()
        if (settings.get("DEBUG", False)): 
            print("Turning on LED Breather")
        self.led_strip_controller = LEDBreather()
        if (settings.get("DEBUG", False)): 
            print("Turning on Fan Controller")
        self.fan_controller = FanController()

    def run_sys(self):
        try:
            self.serial_monitor.start_monitoring()
            self.led_strip_controller.start()
            self.fan_controller.run()
            
            while(True):
                next_purge_time = 0
                next_purge_group = None
                chambers = []
                for group in self.groups:
                    chambers = [c for c in self.chambers.values() if c.group == group]
                    if not chambers:
                        continue
                    if next_purge_time == 0 or (self.groups[group]["last_purge"] + self.groups[group]["purge_interval_s"]) < next_purge_time:
                        next_purge_time = self.groups[group]["last_purge"] + self.groups[group]["purge_interval_s"]
                        next_purge_group = group
                if time.time() > next_purge_time and next_purge_group != None:
                    self.groups[next_purge_group]["last_purge"] = time.time() if len(chambers) != 0 else 0
                    # purge twice
                    self.purge_chambers(chambers=chambers)
                    self.purge_chambers(chambers=chambers)
                    settings["chamber_groups"] = self.groups
                    save_settings()
                else:
                    # sleep until next purge time
                    sleep_time = next_purge_time - time.time()
                    time.sleep(sleep_time)
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received. Stopping control system")
        finally:
            self.shut_sys_down()

    def shut_sys_down(self):
        '''Kills all threads, closes all valves, and turns off the vacuum pump by setting all GPIO pins to LOW'''
        self.reset_valve_pins()
        time.sleep(0.2)
        self.turn_vacuum_off()
        self.serial_monitor.stop_monitoring()
        self.led_strip_controller.stop()
        self.fan_controller.stop()
        GPIO.cleanup()
     
    def add_chamber(self, name: str, group: str, slot: int):
        """
        Initializes a chamber and adds it to the list of chambers for the system to control
        """
        
        for _, chamber in self.chambers.items():
            if chamber.chamber_slot == slot:
                print(f"Tried to add chamber \"{name}\" to slot {slot}, but a chamber is configured for that slot.")
                return
            if chamber.name == name:
                print(f"Tried to add chamber \"{name}\" to slot {slot}, but a chamber with the same name is already configured.")  
                return
            
        if (settings.get("DEBUG", False)): print(f"Adding chamber \"{name}\" to slot {slot}")
        self.chambers[name] = EnvironmentalChamber(name=name, group=group, chamber_slot=slot)
        if slot not in settings["disabled_chambers"]:
            self.serial_monitor.last_readings[name] = {
                "pressure": None,
                "reading": None,
                "alert": None
            }
        else: 
            self.chambers[name].status = "DISABLED"
        

    def purge_chambers(self, chambers: list[EnvironmentalChamber]):
        #  Ignore the next reading from the passed in chambers to avoid sampling during purge
        self.serial_monitor.ignore_next_reading |= {chamber.name: True for chamber in chambers}
        if (settings.get("DEBUG", False)): print(f"Purging chambers in slots {[c.chamber_slot for c in chambers]}")
        # Send a message to the chamber being purged so that it stops gathering data while it's being purged
        # May need to send an initial wake message 
        
        active_chambers = [chamber for chamber in chambers if chamber.status == "NORMAL"]
        if len(active_chambers) == 0:
            print(f"Tried to purge chambers in slots {[c.chamber_slot for c in chambers]} but no chambers were in NORMAL state.")
            return
        else:
            disabled_chambers = [chamber for chamber in chambers if chamber.status == "DISABLED"]
            print(f"Tried to purge the following disabled chambers {[c.chamber_slot for c in disabled_chambers]}")
            
        
        for chamber in active_chambers:
            self.serial_monitor.send_to_all_serial_ports(f"#{chamber.chamber_slot}, purging")
            time.sleep(0.01)
            # open the slenoid valve for the vacuum
            self.open_vacuum_valve(chamber=chamber)
        
        self.turn_vacuum_on()
        vac_unmet = self.wait_for_pressure_lvl(chambers=active_chambers,
                                   pressure_lvl=settings.get("vac_pressure", 101000/25), # default to pretty much 1 atm in pascal
                                   low_pressure=True,
                                   timeout=settings.get("vac_timeout", 5)) # 5 second default timeout

        for chamber in active_chambers:
            self.close_vacuum_valve(chamber=chamber)
        self.turn_vacuum_off()
        for chamber in vac_unmet: # disable chambers that were not able to reach pressure level (likely not sealed properly)
            self.disable_chamber(chamber, "DISABLED")
            active_chambers.remove(chamber)
            # self.serial_monitor.send_to_all_serial_ports(f"#{chamber.chamber_slot}, DISABLED")
            send_discord_alert_webhook(chamber.chamber_slot, "Vacuum pressure not met!")

        time.sleep(1)
        
        for chamber in active_chambers:
            self.open_gas_valve(chamber=chamber)
        gas_unmet = self.wait_for_pressure_lvl(chambers=active_chambers,
                                   pressure_lvl=settings.get("gas_pressure", 101000),
                                   low_pressure=False,
                                   timeout=settings.get("gas_timeout", 5))
        
        for chamber in gas_unmet: # disable chambers that were not able to reach pressure level (likely not sealed properly)
            self.disable_chamber(chamber, "DISABLED")
            active_chambers.remove(chamber)
            # self.serial_monitor.send_to_all_serial_ports(f"#{chamber.slot}, DISABLED")
            send_discord_alert_webhook(chamber.chamber_slot, "Gas pressure not met!")

        for chamber in active_chambers:
            self.close_gas_valve(chamber=chamber)
            # self.serial_monitor.send_to_all_serial_ports(f"#{chamber.chamber_slot}, purge complete")
        if (settings.get("DEBUG", False)): print(f"Finished purging chambers {[chamber.name for chamber in active_chambers]}")

    def disable_chamber(self, chamber: EnvironmentalChamber, new_status: str):
        send_discord_alert_webhook(chamber.name, new_status)
        self.close_gas_valve(chamber=chamber)
        self.close_vacuum_valve(chamber=chamber)
        chamber.status = new_status # DISABLED by convention
        if chamber.chamber_slot not in settings["disabled_chambers"]:
            settings["disabled_chambers"].append(chamber.chamber_slot)
            save_settings()
        if (settings.get("DEBUG", False)): print(f"Disabled Chamber {chamber.chamber_slot} with status {new_status}")
    
    def turn_vacuum_on(self):
        """Turns power to the vacuum pump on by setting its GPIO pin HIGH"""
        self.set_pin_high(self.vacuum_ctrl_pin)
        if (settings.get("DEBUG", False)): print("Vacuum turned ON")
    
    def turn_vacuum_off(self):
        """Turns power to the vacuum pump off by setting its GPIO pin LOW"""
        self.set_pin_low(self.vacuum_ctrl_pin)
        if (settings.get("DEBUG", False)): print("Vacuum turned OFF")
    
    def open_gas_valve(self, chamber: EnvironmentalChamber):
        """Opens the gas valve for the chamber"""
        shift_reg_bit = chamber.chamber_slot * 2
        if chamber.status != "NORMAL":
            # close gas and vacuum valves if status is not normal
            self.close_gas_valve(chamber=chamber)
            self.close_vacuum_valve(chamber=chamber)
            print(f"Tried to open gas valve for chamber {chamber.chamber_slot} but chamber is in {chamber.status} state.")
        else: 
            self.valve_shift_reg.write_bit(bit_num=(chamber.chamber_slot-1)*2, level=GPIO.HIGH)
            if (settings.get("DEBUG", False)): print(f"Chamber {chamber.chamber_slot} gas valve opened")

    def close_gas_valve(self, chamber: EnvironmentalChamber):
        """Closes the gas valve of the chamber"""
        self.valve_shift_reg.write_bit(bit_num=(chamber.chamber_slot-1)*2, level=GPIO.LOW)
        if (settings.get("DEBUG", False)): print(f"Chamber {chamber.chamber_slot} gas valve closed")

    
    def open_vacuum_valve(self, chamber: EnvironmentalChamber):
        """Opens the vacuum valve of the chamber"""
        if chamber.status != "NORMAL":
            # close gas and vacuum valves if status is not normal
            self.close_gas_valve(chamber=chamber)
            self.close_vacuum_valve(chamber=chamber)
            print(f"Tried to open vac valve for chamber {chamber.chamber_slot} but chamber is in {chamber.status} state.")
        else: 
            self.valve_shift_reg.write_bit(bit_num=(chamber.chamber_slot-1)*2+1, level=GPIO.HIGH)
            if (settings.get("DEBUG", False)): print(f"Chamber {chamber.chamber_slot} vac valve opened")

 
    def close_vacuum_valve(self, chamber: EnvironmentalChamber):
        """Closes the vacuum valve of the chamber"""
        self.valve_shift_reg.write_bit(bit_num=(chamber.chamber_slot-1)*2+1, level=GPIO.LOW)
        if (settings.get("DEBUG", False)): print(f"Chamber {chamber.chamber_slot} vac valve closed")

    
    def set_pin_high(self, pin):
        """Sets the GPIO pin HIGH"""
        GPIO.output(pin, GPIO.HIGH)
        if (settings.get("DEBUG", False)): print(f"Pin {pin} set HIGH")
    
    def set_pin_low(self, pin):
        """Sets the GPIO pin LOW"""
        GPIO.output(pin, GPIO.LOW)
        if (settings.get("DEBUG", False)): print(f"Pin {pin} set LOW")
        
    def toggle_pin(self, pin):
        """Toggles the logic level of the GPIO pin"""
        GPIO.output(pin, not GPIO.input(pin))
        if (settings.get("DEBUG", False)): print(f"Pin {pin} toggled")
        
    def reset_valve_pins(self):
        '''Sets all GPIO pins for the solenoid values to LOW'''
        for chamber in self.chambers.values():
            self.close_gas_valve(chamber=chamber)
            self.close_vacuum_valve(chamber=chamber)
        
        GPIO.output(self.vacuum_ctrl_pin, GPIO.LOW)
        if (self.ambient_valve_pin != None): GPIO.output(self.ambient_valve_pin, GPIO.LOW)
        if (settings.get("DEBUG", False)): print(f"Reset valve pins")
    
    def wait_for_pressure_lvl(self, chambers: list[EnvironmentalChamber], pressure_lvl: int, low_pressure: bool, timeout: int) -> list[EnvironmentalChamber]:
        if (settings.get("DEBUG", False)): print(f"Waiting for {"low" if low_pressure else "high"} pressure")
        timeout_time = time.time() + timeout
        
        pressure_unmet = chambers.copy() # list of chambers that haven't met the pressure level yet
        
        while timeout_time > time.time():
            for chamber in pressure_unmet:
                if (pressure := self.serial_monitor.last_readings.get(chamber.name, {}).get("pressure", None)) is not None:
                    try:
                        pressure = float(pressure)
                    except (TypeError, ValueError):
                        pressure = None
                # check that a presssure reading has been received since start up for the chamber
                if (chamber.status != "NORMAL"):
                    if (settings.get("DEBUG", False)): 
                        print(f"""Non-normal chamber status for chamber \"{chamber.name}\" when trying to read pressure
                             Ceasing presssure check for chamber.""")
                    pressure_unmet.remove(chamber)
                elif pressure == None:
                    if (settings.get("DEBUG", False)): 
                        print(f"""No pressure reading for chamber \"{chamber.name}\"",
                          \nWaiting on a {"low" if low_pressure else "high"} pressure threshold.""")
                elif (pressure < pressure_lvl and low_pressure 
                    or pressure > pressure_lvl and not low_pressure
                    ) and chamber in pressure_unmet:
                    pressure_unmet.remove(chamber)
                    self.close_vacuum_valve(chamber=chamber)
                    self.close_gas_valve(chamber=chamber)
                    if (settings.get("DEBUG", False)): print(f"Pressure met for chamber \"{chamber.name}\"")
                    
            if len(pressure_unmet) == 0: return []    
                
            time.sleep(0.01)
        if (settings.get("DEBUG", False)): print(f"Finished waiting for {"low" if low_pressure else "high"} pressure")
        return pressure_unmet
