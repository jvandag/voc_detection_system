import time
import RPi.GPIO as GPIO
from .control_sys.ControlSystem import ControlSystem
from .control_sys.LEDBreather import LEDBreather
from .config.config_manager import settings

def main() -> int:
    led_breather = LEDBreather()
    try:
        control_system = ControlSystem(flush_mode=True)
        chamber_list = {    
            "1":  {"group": "Test 1", "slot": 1},
            "2":  {"group": "Test 1", "slot": 2},
            "3":  {"group": "Test 1", "slot": 3},
            }
        
        print("Adding Chambers")
        for name, kwargs in chamber_list.items():
            control_system.add_chamber(name, **kwargs)
            
        control_system.run_sys()
        # led_breather.start()
        # while(True): time.sleep(0.2)   # Enable serial mesage monitor
        return 0;
    except KeyboardInterrupt:
        print("Keyboard Interrupt, Exiting...")
        # led_breather.stop()
        return 0;