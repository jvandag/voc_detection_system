from queue import Queue
from time import time
import RPi.GPIO as GPIO
import requests
from SerialMonitor import SerialMonitor
from LEDStripController import LEDBreather
from FanController import FanController
import csv
from config.config_manager import settings, save_settings
# from  Demux import DEMUX
from ShiftRegister import ShiftRegister
from EnvironmentalChamber import EnvironmentalChamber

class ControlSystem:
    def __init__(self, vacuum_ctrl_pin: int = None, ambient_valve_pin: int = None):
        GPIO.setmode(GPIO.BOARD)
        self.chambers: dict[str, EnvironmentalChamber] = {}
        # The queue for chamber groups that need to be purged (vacuum and flushed with gas)
        self.purge_queue = Queue()

        self.groups = settings.get("chamber_groups")
        
        # The pin that controls power to the vacuum pump
        self.vacuum_ctrl_pin = vacuum_ctrl_pin or settings.get("vacuum_ctrl_pin")

        self.ambient_valve_pin = ambient_valve_pin  # Unutlized

        self.valve_shift_reg = ShiftRegister(num_bits=16)

        # self.valve_demux = DEMUX(select_pins = settings.get("valve_demux_sel_pins"),
        #                          signal_pin = settings.get("valve_demux_sig_pin"),
        #                          FF_stored = True,
        #                          FF_clk_pin = settings.get("valve_FF_clk_pin"))
        
        # self.chamber_status_demux = DEMUX(select_pins = settings.get("chamber_status_demux_sel_pins"),
        #                                   signal_pin = settings.get("chamber_status_demux_sig_pin"),
        #                                   FF_stored = True,
        #                                   FF_clk_pin = settings.get("chamber_status_FF_clk_pin"))

        GPIO.setup(vacuum_ctrl_pin, GPIO.OUT, initial=GPIO.LOW)
        if ambient_valve_pin != None:
            GPIO.setup(ambient_valve_pin, GPIO.OUT, initial=GPIO.LOW)

        self.serial_monitor = SerialMonitor()
        self.led_strip_controller = LEDBreather()
        self.fan_controller = FanController()

    def run_sys(self):
        try:
            self.serial_monitor.start_monitoring()
            self.led_strip_controller.start()
            self.fan_controller.run()
            # added queue parsing logic here
            while(True):
                next_purge_time = None
                next_purge_group = None
                for group in self.groups:
                    if next_purge_time == None or (self.groups[group]["last_purge"] + self.groups[group]["purge_interval_s"]) < next_purge_time:
                        next_purge_time = self.groups[group]["last_purge"] + self.groups[group]["purge_interval_s"]
                        next_purge_group = group
                sleep_time = time.time() - next_purge_time
                if sleep_time > 0: time.sleep(sleep_time)
                if time.time() > next_purge_time:
                    chambers = [c for c in self.chambers if c.group == next_purge_group]
                    self.purge_chambers(chambers=chambers)
                    self.groups[next_purge_group]["last_purge"] = time.time()
                    settings["chamber_groups"] = next_purge_group
                    save_settings()

        except KeyboardInterrupt:
            print("\nKeyboard interrupt received. Stopping control system")
        finally:
            self.shut_sys_down()

    def shut_sys_down(self):
        '''Kills all threads, closes all valves, and turns off the vacuum pump by setting all GPIO pins to LOW'''
        self.reset_valve_pins()
        self.serial_monitor.stop_monitoring()
        self.led_strip_controller.stop()
        self.fan_controller.stop()
        GPIO.cleanup()
     
    def add_chamber(self, name: str, group: str, slot: int, gas_valve_channel: int, vac_valve_channel: int) -> bool:
        """Initializes a chamber and adds it to the list of chambers for the system to control

        Parameters:
            name (`str`):
                The name of the chamber
            gas_valve_pin (`int`):
                The GPIO pin num used to open and close the gas valve
            vac_valve_pin (`int`):
                The GPIO pin num used to open and close the vacuum valve

        Returns:
            `bool`: 
                `True` if the chamber was successfully added
        """
        if (settings.get("DEBUG", False)): print(f"Adding chamber \"{name}\" to slot {slot}")
        self.chambers[name] = EnvironmentalChamber(name=name, group=group, slot=slot, gas_valve_channel=gas_valve_channel, vac_valve_channel=vac_valve_channel)

        # try:
        #     if name in self.chambers:
        #         raise KeyError(f"Tried to add chamber with name \"{name}\" when an existing chamber with that name already exists")
        #     else:
        #         self.chambers[name] = EnvironmentalChamber(name=name, group=group, slot=slot, gas_valve_channel=gas_valve_channel, vac_valve_channel=vac_valve_channel)
        #         # GPIO.setup([gas_valve_pin, vac_valve_pin], GPIO.OUT, initial=GPIO.LOW)
        #         # self.gas_pins.append(gas_valve_pin)
        #         # self.vacuum_pins.append(vac_valve_pin)
        #         return True
        # except: return False
    

    def purge_chambers(self, chambers: list[EnvironmentalChamber]):
        if (settings.get("DEBUG", False)): print(f"Purging chambers {chambers}")
        # Send a message to the chamber being purged so that it stops gatherint data while it's being purged
        # May need to send an initial wake message 
        for chamber in chambers:
            self.serial_monitor.send_to_all_serial_ports(f"#{chamber.slot}, purging")
            time.sleep(0.01)
            # open the slenoid valve for the vacuum
            self.open_vacuum_valve(chamber=chamber)
        
        self.turn_vacuum_on()
        vac_unmet = self.wait_for_pressure_lvl(chambers=chambers,
                                   pressure_lvl=settings.get("vac_pressure"),
                                   low_pressure=True,
                                   timeout=settings.get("vac_timeout"))
        
        for chamber in vac_unmet: # disable chambers that were not able to reach pressure level (likely not sealed properly)
            self.disable_chamber(chamber, "DISABLED")
            self.serial_monitor.send_to_all_serial_ports(f"#{chamber.slot}, DISABLED")

        for chamber in chambers:
            time.sleep(0.01)
            # open the slenoid valve for the vacuum
            self.close_vacuum_valve(chamber=chamber)
            time.sleep(0.25)
            self.open_gas_valve(chamber=chamber)

        gas_unmet = self.wait_for_pressure_lvl(chambers=chambers,
                                   pressure_lvl=settings.get("gas_pressure"),
                                   low_pressure=False,
                                   timeout=settings.get("gas_timeout"))
        
        for chamber in gas_unmet: # disable chambers that were not able to reach pressure level (likely not sealed properly)
            self.disable_chamber(chamber, "DISABLED")
            self.serial_monitor.send_to_all_serial_ports(f"#{chamber.slot}, DISABLED")

        for chamber in chambers:
            self.close_gas_valve(chamber=chamber)
            time.sleep(0.01)
            self.serial_monitor.send_to_all_serial_ports(f"#{chamber.slot}, purge complete")
        if (settings.get("DEBUG", False)): print(f"Finished purging chambers {chambers}")

    def disable_chamber(self, chamber: EnvironmentalChamber, new_status: str):
        if settings.get("discord_alert_webhook", False): send_discord_alert_webhook(chamber, new_status)
        self.close_gas_valve(chamber=chamber)
        self.close_vacuum_valve(chamber=chamber)
        # self.valve_demux.write(chamber.gas_valve_pin, GPIO.LOW)
        # self.valve_demux.write(chamber.vac_valve_pin, GPIO.LOW)
        chamber.status = new_status # ERROR or DISABLED by convention
        # light up error light
        #self.chamber_status_demux.write(2*chamber.slot, GPIO.HIGH)
        if (settings.get("DEBUG", False)): print(f"Disabled Chamber {chamber.slot} with status {new_status}")
    
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
        shift_reg_bit = chamber.slot * 2
        if chamber.status != "NORMAL":
            # close gas and vacuum valves if status is not normal
            self.close_gas_valve(chamber=chamber)
            self.close_vacuum_valve(chamber=chamber)
            #self.valve_demux.write(chamber.gas_valve_pin, GPIO.LOW)
            print(f"Tried to open gas valve for chamber {chamber.slot} but chamber is in {chamber.status} state.")
        else: 
            self.valve_shift_reg.write_bit(bit_num=chamber.slot*2, level=GPIO.HIGH)
            # self.valve_demux.write(chamber.gas_valve_pin, GPIO.HIGH)
            if (settings.get("DEBUG", False)): print(f"Chamber {chamber.slot} gas valve opened")

    def close_gas_valve(self, chamber: EnvironmentalChamber):
        """Closes the gas valve of the chamber"""
        self.valve_shift_reg.write_bit(bit_num=chamber.slot*2, level=GPIO.LOW)
        # self.valve_demux.write(chamber.gas_valve_pin, GPIO.LOW)
        if (settings.get("DEBUG", False)): print(f"Chamber {chamber.slot} gas valve closed")

    
    def open_vacuum_valve(self, chamber: EnvironmentalChamber):
        """Opens the vacuum valve of the chamber"""
        if chamber.status != "NORMAL":
            # close gas and vacuum valves if status is not normal
            self.close_gas_valve(chamber=chamber)
            self.close_vacuum_valve(chamber=chamber)
            # self.valve_demux.write(chamber.vac_valve_pin, GPIO.LOW)
            print(f"Tried to open vac valve for chamber {chamber.slot} but chamber is in {chamber.status} state.")
        else: 
            self.valve_shift_reg.write_bit(bit_num=chamber.slot*2+1, level=GPIO.HIGH)
            # self.valve_demux.write(chamber.vac_valve_pin, GPIO.HIGH)
            if (settings.get("DEBUG", False)): print(f"Chamber {chamber.slot} vac valve opened")

            
    def close_vacuum_valve(self, chamber: EnvironmentalChamber):
        """Closes the vacuum valve of the chamber"""
        self.valve_shift_reg.write_bit(bit_num=chamber.slot*2+1, level=GPIO.LOW)
        # self.valve_demux.write(chamber.vac_valve_pin, GPIO.LOW)
        if (settings.get("DEBUG", False)): print(f"Chamber {chamber.slot} vac valve closed")

    
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
        '''Sets all GPIO pins on the board to LOW'''
        for chamber in self.chambers:
            self.close_gas_valve(chamber=chamber)
            self.close_vacuum_valve(chamber=chamber)
            # self.valve_demux.write(chamber.gas_valve_pin, GPIO.LOW)
            # self.valve_demux.write(chamber.vac_valve_pin, GPIO.LOW)
        
        GPIO.output(self.vacuum_ctrl_pin, GPIO.LOW)
        if (self.ambient_valve_pin != None): GPIO.output(self.ambient_valve_pin, GPIO.LOW)
        if (settings.get("DEBUG", False)): print(f"Reset valve pins")
    
    def wait_for_pressure_lvl(self, chambers: list[EnvironmentalChamber], pressure_lvl: int, low_pressure: bool, timeout: int) -> list[int]:
        if (settings.get("DEBUG", False)): print(f"Waiting for {"low" if low_pressure else "high"} pressure")
        timeout_time = time.time() + timeout
        
        pressure_unmet = chambers.copy() # list of chambers that haven't met the pressure level yet
        # for chamber in chambers:
        #     pressure_unmet.append(chamber.slot)
        
        file_path = f"control_data/pressure_log"
        already_read = 0
        while timeout_time > time.time():
            try:
                with open(file_path, newline='') as csvfile:
                    reader = list(csv.reader(csvfile))
                    new_rows = reader[already_read:]
                    for row in new_rows:
                        slot = row[0] # should contain the chamber slot number
                        pressure = row[1]
                        current_chamber = next((chamber for chamber in chambers if chamber.slot == int(slot)), None)
                        # low pressure bool indicates that we want pressure less than pressure level
                        if (pressure < pressure_lvl and (current_chamber in pressure_unmet)) == low_pressure:
                            pressure_unmet.remove(current_chamber)
                            self.close_vacuum_valve(chamber=current_chamber)
                            self.close_gas_valve(chamber=current_chamber)
                    if len(pressure_unmet) == 0: return []
                    already_read = len(reader)
            except FileNotFoundError:
                print("CSV file not found. Waiting...")
            except Exception as e:
                print(f"Error reading CSV: {e}")

            time.sleep(0.05)
            if (settings.get("DEBUG", False)): print(f"Finished waiting for {"low" if low_pressure else "high"} pressure")
        return pressure_unmet


def send_discord_alert_webhook(chamber: int, new_status: str) -> bool:
    """
    Sends a message to a Discord webhook URL.

    Parameters:
        chamber (`int`): 
            The chamber slot number
        new_status: (`str`): 
            The new status of the chamber

    Returns:
        `bool`: True if the message was sent successfully, False otherwise.
    """
    wh = settings.get("discord_alert_webhook", False)
    if not wh: return False

    payload = {
        "content": f"Chamber {chamber} status changed to {new_status}"
    }
    if (settings.get("DEBUG", False)): print(f"Sending \"{payload.content}\" to webhook {wh}")
    try:
        response = requests.post(wh, json=payload)
        return response.status_code == 204  # Discord returns 204 No Content on success
    except requests.exceptions.RequestException as e:
        print(f"Error sending webhook: {e}")
        return False
    