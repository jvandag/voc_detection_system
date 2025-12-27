"""
Tests that all of the system components are connected correctly and able
to be interfaced with. Does not check ControlSystem
"""
from .control_sys.ControlSystem import ControlSystem
from time import sleep
import RPi.GPIO as GPIO
from .config.config_manager import settings

def main() -> int:
    print("starting")
    try:
        # Initialize control system
        control_sys = ControlSystem()
    except Exception as e:
        print(f"Error initializing Control System: {e}")
        return 1
    
    try:
        chamber_list = {    
            "1":            {"group": "Test 1", "slot": 1},
            "Light Roast":  {"group": "Test 2", "slot": 2},
            "Medium Roast": {"group": "Test 1", "slot": 3},
            "Dark Roast":   {"group": "Test 1", "slot": 4}
            }
        
        
        # Add chambers
        # for key in chamber_list:
        #     control_sys.add_chamber(key, chamber_list[key][0], chamber_list[key][1])
        
        print("Adding Chambers")
        for name, kwargs in chamber_list.items():
            control_sys.add_chamber(name, **kwargs)
            
        control_sys.add_chamber("1", "Test 1", 1)
        control_sys.add_chamber("2", "Test 1", 1)
        control_sys.add_chamber("1", "Test 1", 6)
        
        control_sys.turn_vacuum_on();
        sleep(1)
        
        print("Openning Valves")
        for chamber in control_sys.chambers.values():
            control_sys.open_gas_valve(chamber)
            sleep(0.5)
            control_sys.open_vacuum_valve(chamber)
            sleep(0.5)
            control_sys.close_gas_valve(chamber)
            sleep(0.5)
            control_sys.close_vacuum_valve(chamber)
            sleep(1)
        control_sys.turn_vacuum_off();
        sleep(1)
            
        control_sys.run_sys()
        
    except KeyboardInterrupt:
        print("\nKeyboard Interupt, Gracefully Stopping...")
        control_sys.shut_sys_down()
        return 0
    finally:
        pass
        # print("Turning fans off")
        # fan_controller.stop()
        # print("Turning LED strip off")
        # led_breather.stop()
        # print("Stopping serial monitor")
        # serial_monitor.stop_monitoring()
        # print("Completed System Test!")
        return 0

if __name__ == "__main__":
    exit(main())
