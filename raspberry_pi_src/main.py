import time
import RPi.GPIO as GPIO
from control_sys.ControlSystem import ControlSystem
from config.config_manager import settings

if __name__ == "__main__":
    control_system = ControlSystem()
    control_system.run_sys()
    