import time
import RPi.GPIO as GPIO
from .control_sys.ControlSystem import ControlSystem
from .control_sys.LEDBreather import LEDBreather
from .config.config_manager import settings

def main() -> int:
    led_breather = LEDBreather()
    try:
        control_system = ControlSystem()
        control_system.run_sys()
        # led_breather.start()
        # while(True): time.sleep(0.2)   # Enable serial mesage monitor
        return 0;
    except KeyboardInterrupt:
        print("Keyboard Interrupt, Exiting...")
        # led_breather.stop()
        return 0;