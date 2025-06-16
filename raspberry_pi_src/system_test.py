from control_sys.LEDStripController import LEDBreather
from control_sys.Mux import MUX
from control_sys.FanController import FanController
import time
import RPi.GPIO as GPIO
from config.config_manager import settings

def set_LED(LED_address: int, LED_mux: MUX, clk_mux: MUX, value:int):
    LED_mux.write(channel=LED_address, value=value)
    clk_mux.pos_edge(LED_address)
    LED_mux.write(LED_address, GPIO.LOW)


if __name__ == "__main__":
    fan_controller = FanController()
    
    # power on indicator LED
    power_LED_pin = settings.get("power_on_LED_pin")
    vac_relay_pin = settings.get("vac_relay_pin")
    
    # get the pins for the muxes from the settings
    # BCM-numbered GPIO pins for S0…S3, and the shared SIG line:
    gas_sel_pins = settings.get("gas_valve_mux_sel_pins")
    gas_sig_pin  = settings.get("gas_valve_mux_sig_pin")
    
    vac_sel_pins = settings.get("gas_valve_mux_sel_pins")
    vac_sig_pin  = settings.get("gas_valve_mux_sig_pin")
    
    cham_stat_sel_pins = settings.get("chamber_status_mux_sel_pins")
    cham_stat_sig_pin  = settings.get("chamber_status_mux_sig_pins")
    FF_clk_sig_pin     = settings.get("FF_clk_mux_sig_pin")
    

    # Initialize muxes
    gas_mux     = MUX(select_pins=gas_sel_pins, signal_pin=gas_sig_pin, gpio_mode=GPIO.BCM)
    vac_mux     = MUX(select_pins=vac_sel_pins, signal_pin=vac_sig_pin, gpio_mode=GPIO.BCM)
    stat_mux    = MUX(select_pins=cham_stat_sel_pins, signal_pin=cham_stat_sig_pin, gpio_mode=GPIO.BCM)
    # FF_clk_mux controls the clock for the flip flops that latch the status LED light state,
    # the select pins are shared with stat_mux
    FF_clk_mux  = MUX(select_pins=cham_stat_sel_pins, signal_pin=FF_clk_sig_pin, gpio_mode=GPIO.BCM)
    
    # toggle fans
    fan_controller.run(use_thresh=False)
    time.sleep(3)
    fan_controller.stop()
    
    # Turn on power on LED
    GPIO.setup(power_LED_pin, GPIO.OUT)
    GPIO.output(power_LED_pin, GPIO.HIGH)
    
    # Check that vacuum relay works
    GPIO.setup(vac_relay_pin, GPIO.OUT)
    GPIO.output(vac_relay_pin, GPIO.HIGH)
    
    # test functionality of each status LED and each chamber solenoid
    for i in range(8):
        # For the i-th chamber:
        # turn on both status LEDs
        set_LED(i*2, stat_mux, FF_clk_mux, GPIO.HIGH)
        time.sleep(1)
        set_LED(i*2+1, stat_mux, FF_clk_mux, GPIO.HIGH)
        time.sleep(1)
        
        # open gas valve solenoid
        gas_mux.write(i, GPIO.HIGH)
        time.sleep(1)
        # close gas valve solenoid
        gas_mux.write(i, GPIO.LOW)
        time.sleep(0.5)
        # open vac valve solenoid
        vac_mux.write(i, GPIO.HIGH)
        time.sleep(1)
        # close gas valve solenoid
        vac_mux.write(i, GPIO.LOW)
        # Turn off both status LEDs
        set_LED(i*2, stat_mux, FF_clk_mux, GPIO.LOW)
        time.sleep(0.5)
        set_LED(i*2+1, stat_mux, FF_clk_mux, GPIO.LOW)
   
    # RUN QUEUE FUNCTIONALITY CHECK AFTER IT IS IMPLEMENTED
