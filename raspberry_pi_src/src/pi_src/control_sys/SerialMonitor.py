import serial
import threading
import time
import csv
from serial.tools import list_ports
from ..config.config_manager import settings
from .DiscordAlerts import send_discord_alert_webhook


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

        # port_name -> Thread
        self.active_ports = {}
        self.lock = threading.Lock()
        self.running = False
        self.last_readings = {}
        self.monitor_thread = None

    def read_from_port(self, port_name):
        ser = None
        try:
            ser = serial.Serial(port_name, self.baud_rate, timeout=1.0)
        except serial.SerialException as e:
            print(f"Could not open {port_name}: {e}")
            # Make sure this port is not considered active
            with self.lock:
                self.active_ports.pop(port_name, None)
            return

        try:
            print(f"Started listening on {port_name}")
            # Clear any stale data in the buffer
            try:
                ser.reset_input_buffer()
            except Exception:
                pass

            while self.running and ser.is_open:
                # Block until a line arrives or timeout
                raw = ser.readline()
                if not raw:
                    # Timeout with no data
                    if not self.running:
                        break
                    continue
                try:
                    line = raw.decode('utf-8', errors='ignore').strip()
                except Exception:
                    continue
                if line:
                    self.parse_serial_msg(line)
                    
        except Exception as e:
            print(f"Error on {port_name}: {e}")
        finally:
            try:
                if ser is not None and ser.is_open:
                    ser.close()
            except Exception:
                pass
            with self.lock:
                self.active_ports.pop(port_name, None)
            print(f"Stopped listening on {port_name}")

    def parse_serial_msg(self, data: str):
        if self.print_msgs:
            print(f"{data}")
        # save to appropriate CSV based off of message

        if self.save_data:
            # Split the string into a list (assuming comma-and-space-separated values)
            col = data.split(', ')
            if not col:
                return

            match col[0]:
                case "##PRESSURE":
                    # check chamber has been added by control system
                    if self.last_readings.get(col[1], None) is not None:
                        self.last_readings[col[1]]["pressure"] = col[2]
                    else:
                        print(f"Pressure reading recived for chamber \"{col[1]}\" but chamber is uninitialized.")
                case "##READING":
                    # check chamber has been added by control system
                    if self.last_readings.get(col[1], None) is not None:
                        self.last_readings[col[1]]["reading"] = col[2]
                        # save reading to csv file specific to the chamber
                        file_path = f"chamber_{col[1]}_readings.csv"
                        with open(file_path, mode='a', newline='', encoding='utf-8') as file:
                            writer = csv.writer(file)
                            writer.writerow(col)
                        print(f"Data appended to {file_path}")
                    else:
                        print(f"Sensor reading(s) recived for chamber \"{col[1]}\" but chamber is uninitialized:\n\t{data}")
                case "##ALERT":
                    # check chamber has been added by control system
                    if self.last_readings.get(col[1], None) is not None:
                        self.last_readings[col[1]]["alert"] = col[2]
                        send_discord_alert_webhook(col[1], col[2])
                    else:
                        print(f"Alert received for chamber \"{col[1]}\" but chamber is uninitialized:\n\t{data}")
                        if settings.get("DEBUG", False):
                            send_discord_alert_webhook(col[1], col[2])

    def start_monitoring(self, monitor_interval: int = 2):
        if self.running:
            return  # already running

        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_ports,
            args=(monitor_interval,),
            daemon=False,  # non-daemon so we can join it cleanly
        )
        self.monitor_thread.start()

    def stop_monitoring(self, join_timeout: float = 3.0):
        # Tell all threads to stop
        self.running = False

        # Wait for monitor thread to exit
        t = self.monitor_thread
        if t is not None:
            t.join(timeout=join_timeout)

        # Wait for per-port reader threads to exit
        with self.lock:
            threads = list(self.active_ports.values())
        for th in threads:
            th.join(timeout=join_timeout)

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
        ports = list_ports.comports()
        for port in ports:
            try:
                with serial.Serial(port.device, baudrate=baudrate, timeout=timeout) as ser:
                    ser.write(message.encode('utf-8'))
                    print(f"Sent to {port.device}")
            except serial.SerialException as e:
                print(f"Failed to send to {port.device}: {e}")
        if settings.get("DEBUG", False):
            print(f"Sent \"{message}\" to all serial ports")

    def _monitor_ports(self, monitor_interval=2):
        # Scan for ports only while monitoring is active
        while self.running:
            ports = [port.device for port in list_ports.comports()]

            with self.lock:
                if not self.running:
                    break

                for port in ports:
                    if port not in self.active_ports:
                        t = threading.Thread(
                            target=self.read_from_port,
                            args=(port,),
                            daemon=False,  # non-daemon so we can join on stop
                        )
                        self.active_ports[port] = t
                        t.start()

            # Sleep in small chunks so we can react quickly to stop_monitoring()
            elapsed = 0.0
            while self.running and elapsed < monitor_interval:
                time.sleep(0.1)
                elapsed += 0.1


def main() -> int:
    monitor = SerialMonitor()
    try:
        print("Starting Serial Monitor. Press Ctrl+C to stop.")
        monitor.start_monitoring()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")
        monitor.stop_monitoring()
        print("Exited.")
        return 0
    return 0


if __name__ == "__main__":
    exit(main())
