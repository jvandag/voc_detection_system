import RPi.GPIO as GPIO
import time

def main():
    pin = 4
    # GPIO setup
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(pin, GPIO.OUT)
    
    while True:
        GPIO.output(pin, GPIO.LOW)
        time.sleep(0.5)
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(0.5)

if __name__ == "__main__":
    main()
