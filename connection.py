import os
import time

import serial.tools.list_ports
from pymavlink import mavutil

LAST_PORT_FILE = os.path.expanduser("~/.last_mavlink_port")


def list_serial_ports():
    ports = serial.tools.list_ports.comports()
    return [port.device for port in ports]


def find_ardupilot_port(baud_rate=57600, timeout=2):
    ports = list_serial_ports()
    print("Scanning ports:", ports)
    last_used_port = None
    if os.path.exists(LAST_PORT_FILE):
        with open(LAST_PORT_FILE, "r") as f:
            last_used_port = f.read().strip()

    if last_used_port and (index := ports.index(last_used_port)):
        ports.pop(index)
        ports.insert(0, last_used_port)

    for port in ports:
        print(f"Trying port: {port}")
        try:
            # Attempt to connect to the port
            connection = mavutil.mavlink_connection(port, baud=baud_rate)
            start_time = time.time()
            while time.time() - start_time < timeout:
                # Check for a heartbeat message
                if connection.wait_heartbeat(timeout=1):
                    print(
                        f"Heartbeat received from system (system {connection.target_system} component {connection.target_component}) on port {port}"
                    )
                    with open(LAST_PORT_FILE, "w") as f:
                        f.write(f"{port}")
                    return connection
            print(f"No heartbeat on port {port} within {timeout} seconds")
        except Exception as e:
            print(f"Error connecting to port {port}: {e}")

    print("No ArduPilot device found on any port.")
    return None


# connection = find_ardupilot_port()

# if connection:
#     print("ArduPilot device found!")
# else:
#     print("ArduPilot device not found.")
