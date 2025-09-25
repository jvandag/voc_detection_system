"""
Tests that all of the system components are connected correctly and able
to be interfaced with. Does not check ControlSystem
"""
from control_sys.LEDStripController import LEDBreather
from control_sys.SerialMonitor import SerialMonitor
from control_sys.ShiftRegister import ShiftRegister
# from control_sys.Demux import DEMUX
from control_sys.FanController import FanController
import time
import RPi.GPIO as GPIO
from config.config_manager import settings

if __name__ == "__main__":
    fan_controller = FanController()
    
    print("Getting on power indicator LED pin")
    power_LED_pin = settings.get("power_on_LED_pin")
    print("Getting vacuum control pin")
    vacuum_ctrl_pin = settings.get("vacuum_ctrl_pin")
    
    # Turn LED breather on
    print("Turning LED strip on")
    led_breather = LEDBreather()
    led_breather.start()

    # Enable serial mesage monitor
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
    
    # Turn on power on LED
    print("Turning power indicator LED on")
    GPIO.setup(power_LED_pin, GPIO.OUT)
    GPIO.output(power_LED_pin, GPIO.HIGH)
    
    # Check that vacuum relay works
    print("Turning vacuum on")
    GPIO.setup(vacuum_ctrl_pin, GPIO.OUT)
    GPIO.output(vacuum_ctrl_pin, GPIO.HIGH)
    time.sleep(3)
    print("Turning vacuum off")
    GPIO.output(vacuum_ctrl_pin, GPIO.LOW)
    
    # Test shift reg opens valves
    shift_reg.set_all_low()
    for i in range(8):
        # open and close both valves for each chamber
        print(f"Opening gas valve for chamber {i}")
        shift_reg.write_bit(bit_num = 2*i, level = GPIO.HIGH)
        time.sleep(1)
        print(f"Opening vac valve for chamber {i}")
        shift_reg.write_bit(bit_num = 2*i+1, level = GPIO.HIGH)
        time.sleep(1)
        print(f"Closing valves for chamber {i}")
        shift_reg.overwrite_buffer(bit_nums=[])
        time.sleep(1)

    print("Stopping serial monitor")
    serial_monitor.stop_monitoring()
    print("Turning LED strip off")
    led_breather.stop()
    print("Completed System Test!")


    # DEMUX Hook up for valves
    # print("Initialiing demuxes")
    # valve_demux = DEMUX(select_pins = settings.get("valve_demux_sel_pins"),
    #                             signal_pin = settings.get("valve_demux_sig_pin"),
    #                             FF_stored = True,
    #                             FF_clk_pin = settings.get("valve_FF_clk_pin"))
    
    # chamber_status_demux = DEMUX(select_pins = settings.get("chamber_status_demux_sel_pins"),
    #                              signal_pin = settings.get("chamber_status_demux_sig_pin"),
    #                              FF_stored = True,
    #                              FF_clk_pin = settings.get("chamber_status_FF_clk_pin"))
    # # # test functionality of each status LED and each chamber solenoid
    # for i in range(8):
    #     # For the i-th chamber:
    #     # turn on both status LEDs
    #     print(f"Turning ON LED on demux channel {i*2}")
    #     chamber_status_demux.write(i*2, GPIO.HIGH)
    #     time.sleep(1)
    #     print(f"Turning ON LED on demux channel {i*2+1}")
    #     chamber_status_demux.write(i*2+1, GPIO.HIGH)
    #     time.sleep(1)

    #     print(f"Turning OFF LED on demux channel {i*2}")
    #     chamber_status_demux.write(i*2, GPIO.LOW)
    #     time.sleep(1)
    #     print(f"Turning OFF LED on demux channel {i*2+1}")
    #     chamber_status_demux.write(i*2+1, GPIO.LOW)
    #     time.sleep(1)
        
    #     # open each solenoid valve
    #     print(f"Opening valve on demux channel {i*2}")
    #     valve_demux.write(i*2, GPIO.HIGH)
    #     time.sleep(1)
    #     print(f"Opening valve on demux channel {i*2+1}")
    #     valve_demux.write(i*2+1, GPIO.HIGH)
    #     time.sleep(1)

    #     print(f"Closing valve on demux channel {i*2}")
    #     valve_demux.write(i*2, GPIO.LOW)
    #     time.sleep(1)
    #     print(f"Closing valve on demux channel {i*2+1}")
    #     valve_demux.write(i*2+1, GPIO.LOW)
    #     time.sleep(1)
