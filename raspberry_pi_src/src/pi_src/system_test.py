"""
Tests that all of the system components are connected correctly and able
to be interfaced with. Does not check ControlSystem
"""
from .control_sys.LEDBreather import LEDBreather
from .control_sys.SerialMonitor import SerialMonitor
from .control_sys.ShiftRegister import ShiftRegister
from .control_sys.FanController import FanController
import time
import RPi.GPIO as GPIO
from .config.config_manager import settings

def main() -> int:
    
    try:
        fan_controller = FanController()
        
        # print("Getting on power indicator LED pin")
        # power_LED_pin = settings.get("power_on_LED_pin")
        # print("Getting vacuum control pin")
        # vacuum_ctrl_pin = settings.get("vacuum_ctrl_pin")
        
        # Turn LED breather on
        print("Turning LED strip on")
        led_breather = LEDBreather()
        led_breather.start()
        time.sleep(5)    # Enable serial mesage monitor
        print("Enabling serial monitor")
        serial_monitor = SerialMonitor(print_msgs=True, save_data=False)
        serial_monitor.start_monitoring(monitor_interval=1)

        shift_reg = ShiftRegister(num_bits = 16)
        
        # Toggle fans
        print("Turning fans on")
        fan_controller.run(use_thresh=False)
        time.sleep(3)
        print("Turning fans off")
        fan_controller.stop()
        
        # print("Turning fans off")
        # fan_controller.stop()
        # time.sleep(1)
        
        # Check that vacuum relay works
        # print("Turning vacuum on")
        # GPIO.setup(vacuum_ctrl_pin, GPIO.OUT)
        # GPIO.output(vacuum_ctrl_pin, GPIO.HIGH)
        # time.sleep(3)
        # print("Turning vacuum off")
        # GPIO.output(vacuum_ctrl_pin, GPIO.LOW)
        
        # Test shift reg opens valves
        shift_reg.set_all_low()
        for i in range(6):
            # open and close both valves for each chamber
            print(f"Opening gas valve for chamber {i+1}")
            shift_reg.write_bit(bit_num = 2*i, level = GPIO.HIGH)
            time.sleep(1)
            print(f"Opening vac valve for chamber {i+1}")
            shift_reg.write_bit(bit_num = 2*i+1, level = GPIO.HIGH)
            time.sleep(1)
            print(f"Closing valves for chamber {i+1}")
            shift_reg.overwrite_buffer(bit_nums=[])
            time.sleep(1)

        # print("Stopping serial monitor")
        # serial_monitor.stop_monitoring()
        
        # while (True): time.sleep(1)
        # print("Turning LED strip off")
        # led_breather.stop()
        # print("Completed System Test!")
        
    except KeyboardInterrupt:
        print("\nKeyboard Interupt, Gracefully Stopping...")
        shift_reg.set_all_low()
    finally:
        print("Turning fans off")
        fan_controller.stop()
        print("Turning LED strip off")
        led_breather.stop()
        print("Stopping serial monitor")
        serial_monitor.stop_monitoring()
        print("Completed System Test!")
        return 0

if __name__ == "__main__":
    exit(main())
