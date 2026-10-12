import serial
import threading
import time
import csv
import os
from typing import Optional
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
                 save_data=True,
                 log_uninitialized_chambers=False # will log data from chambers that are not initialized if true
                 ):

        self.baud_rate = baud_rate or settings.get("serial_monitor_baud_rate", 115200)
        self.print_msgs = print_msgs
        self.save_data = save_data
        self.log_uninitialized = log_uninitialized_chambers

        # port_name -> Thread
        self.active_ports = {}
        # Canonical device name -> open connection, shared by reader and sender.
        self.connections = {}
        self.lock = threading.Lock()
        self.print_lock = threading.Lock()
        self.running = False
        self.last_readings = {}
        self.monitor_thread = None
        self.ignore_next_reading = {}

    def _print(self, message: str):
        with self.print_lock:
            print(message)

    def read_from_port(self, port_name):
        ser = None
        try:
            options = {"exclusive": True} if os.name == "posix" else {}
            ser = serial.Serial(port_name, self.baud_rate, timeout=1.0,
                                write_timeout=1.0, **options)
        except serial.SerialException as e:
            self._print(f"Could not open {port_name}: {e}")
            # Make sure this port is not considered active
            with self.lock:
                self.active_ports.pop(port_name, None)
            return

        try:
            with self.lock:
                self.connections[port_name] = ser
            self._print(f"Started listening on {port_name}")
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
                    try:
                        self.parse_serial_msg(line, port_name)
                    except Exception as e:
                        # A CSV/alert failure must not reopen/reset a healthy device.
                        self._print(f"Could not process message from {port_name}: {e}")
                    
        except Exception as e:
            self._print(f"Error on {port_name}: {e}")
        finally:
            # Serialize closing against command writes to this connection.
            with self.lock:
                self.connections.pop(port_name, None)
                try:
                    if ser is not None and ser.is_open:
                        ser.close()
                except Exception:
                    pass
                self.active_ports.pop(port_name, None)
            self._print(f"Stopped listening on {port_name}")

    def parse_serial_msg(self, data: str, port_name: Optional[str] = None):
        if self.print_msgs:
            source = f"[{port_name}] " if port_name else ""
            self._print(f"{source}{data}")
        elif not data.startswith(("##READING,", "##PRESSURE,")):
            # Keep sensor errors and boot diagnostics visible in chamber mode.
            self._print(f"[{port_name or 'serial'}] {data}")
        # save to appropriate CSV based off of message
        if self.save_data:
            # Split the string into a list (assuming comma separated values)
            col = data.split(',')
            # Firmware alerts/pressure messages can have spaces after commas.
            col = [field.strip() for field in col]
            if not col:
                return

            match col[0]:
                case "##PRESSURE":
                    if len(col) < 3:
                        return
                    # check chamber has been added by control system
                    if self.last_readings.get(col[1], None) is not None:
                        self.last_readings[col[1]]["pressure"] = col[2]
                    else:
                        # if (settings.get("DEBUG", False)): print(f"Pressure reading recived for chamber \"{col[1]}\" but chamber is uninitialized.")
                        pass
                case "##READING":
                    if len(col) != 27:
                        self._print(f"Dropped malformed reading from {port_name or 'serial'}: {data}")
                        return
                    # check chamber has been added by control system
                    if self.last_readings.get(col[1], None) is not None or self.log_uninitialized:
                        if self.ignore_next_reading.get(col[1], False):
                            self.ignore_next_reading[col[1]] = False
                            if (settings.get("DEBUG", False)): self._print(f"Ignoring sensor reading for chamber \"{col[1]}\"")
                            return
                        if self.last_readings.get(col[1], None) is not None:
                            self.last_readings[col[1]]["reading"] = col[2]
                        # save reading to csv file specific to the chamber
                        file_path = f"data/chamber_{col[1]}_readings.csv"
                        
                        # replace the reading flag with a timestamp
                        col[0] = str(int(time.time()))
                        with open(file_path, mode='a', newline='', encoding='utf-8') as file:
                            writer = csv.writer(file)
                            writer.writerow(col)
                        self._print(f"Data appended to {file_path}")
                    else:
                        self._print(f"Sensor reading(s) received for chamber \"{col[1]}\" but chamber is uninitialized:\n\t{data}")
                case "##ALERT":
                    if len(col) < 3:
                        return
                    # check chamber has been added by control system
                    if self.last_readings.get(col[1], None) is not None:
                        self.last_readings[col[1]]["alert"] = col[2]
                        send_discord_alert_webhook(col[1], col[2])
                    else:
                        if settings.get("DEBUG", False):
                            self._print(f"Alert received for chamber \"{col[1]}\" but chamber is uninitialized:\n\t{data}")
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

        During monitoring, sends through the existing open connections only.
        Commands to devices that are not yet connected are not queued. The
        baudrate/timeout arguments apply to standalone sends, when stopped.

        Parameters:
            message (`str`):
            The message to send.
            baudrate (`int`):
            Baud rate for serial communication.
            timeout (`float`):
            Timeout for opening the serial port.
        """
        if self.running:
            # Opening another handle can steal data and toggle reset lines.
            with self.lock:
                if not self.connections:
                    self._print("No open serial connections; command was not sent")
                for port_name, ser in self.connections.items():
                    try:
                        ser.write(message.encode('utf-8'))
                        self._print(f"Sent to {port_name}")
                    except (serial.SerialException, OSError) as e:
                        self._print(f"Failed to send to {port_name}: {e}")
            return

        ports = self._available_ports()
        for port in ports:
            try:
                options = {"exclusive": True} if os.name == "posix" else {}
                with serial.Serial(port, baudrate=baudrate, timeout=timeout,
                                   write_timeout=timeout, **options) as ser:
                    ser.write(message.encode('utf-8'))
                    self._print(f"Sent to {port}")
            except serial.SerialException as e:
                self._print(f"Failed to send to {port}: {e}")
        if settings.get("DEBUG", False):
            self._print(f"Sent \"{message}\" to all serial ports")

    def _available_ports(self):
        # udev aliases such as /dev/ttyUSB_ also match pySerial's Linux glob.
        # Key by the resolved path so aliases cannot create competing readers.
        return sorted({os.path.realpath(port.device) if os.name == "posix" else port.device
                       for port in list_ports.comports()})

    def _monitor_ports(self, monitor_interval=2):
        # Scan for ports only while monitoring is active
        while self.running:
            ports = self._available_ports()

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
    monitor = SerialMonitor(baud_rate=None, print_msgs=True, save_data=True, log_uninitialized_chambers=True)
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
