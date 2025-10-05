import serial
import threading
import time
import csv
from serial.tools import list_ports
from config.config_manager import settings

class SerialMonitor:
    """
    Monitors all serial ports and stores sensor data messages in their
    designated csv files
    """
    def __init__(self,
                 baud_rate=None,
                 print_msgs=False,
                 save_data=True):
        
        self.baud_rate = baud_rate or settings.get("serial_monitor_baud_rate", 115200)
        self.print_msgs = print_msgs
        self.save_data = save_data
        self.active_ports = {}
        self.lock = threading.Lock()
        self.running = False

    def read_from_port(self, port_name):
        try:
            ser = serial.Serial(port_name, self.baud_rate, timeout=1)
            print(f"Started listening on {port_name}")
            while True:
                if not ser.is_open:
                    break
                if ser.in_waiting:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    self.parse_serial_msg(line)
        except Exception as e:
            print(f"Error on {port_name}: {e}")
        finally:
            with self.lock:
                if port_name in self.active_ports:
                    del self.active_ports[port_name]
            print(f"Stopped listening on {port_name}")

    def parse_serial_msg(self, data: str):
        if (self.print_msgs): print(f"{data}")
        # save to appropriate CSV based off of message

        if self.save_data:
            # Split the string into a list (assuming comma-separated values)
            row = data.split(',')
            file_path = f"test_file.csv"
            # read first item in row to figure what the data is for.
            # Open the file in append mode
            with open(file_path, mode='a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(row)

            print(f"Data appended to {file_path}")

    def start_monitoring(self, monitor_interval: int = 2):
        if not self.running:
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_ports, args=(monitor_interval,), daemon=True)
            self.monitor_thread.start()

    def stop_monitoring(self):
        self.running = False
        if self.monitor_thread is not None:
            self.monitor_thread.join()

    def send_to_all_serial_ports(self, message: str, baudrate: int = 115200, timeout: float = 1.0):
        """
        Sends a string message to all available serial ports.

        Parameters:
            message (`str`):
            The message to send.
            baudrate (`int`):
            Baud rate for serial communication.
            timeout (`float`):
            Timeout for opening the serial port.
        """
        ports = serial.tools.list_ports.comports()
        for port in ports:
            try:
                with serial.Serial(port.device, baudrate=baudrate, timeout=timeout) as ser:
                    ser.write(message.encode('utf-8'))
                    print(f"Sent to {port.device}")
            except serial.SerialException as e:
                print(f"Failed to send to {port.device}: {e}")
        if (settings.get("DEBUG", False)): print(f"Sent \"{message}\" to all serial ports")

    def _monitor_ports(self, monitor_interval = 2):
        while True:
            ports = [port.device for port in list_ports.comports()]
            with self.lock:
                for port in ports:
                    if port not in self.active_ports:
                        t = threading.Thread(target=self.read_from_port, args=(port,))
                        t.daemon = True
                        self.active_ports[port] = t
                        t.start()
            time.sleep(monitor_interval)  # Adjust scan interval as needed

if __name__ == "__main__":
    try:
        print("Starting Serial Monitor. Press Ctrl+C to stop.")
        monitor = SerialMonitor()
        monitor._monitor_ports()
    except KeyboardInterrupt:
        print("Exiting...")
