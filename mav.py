MAV_TYPE = {
    1: "Fixed-wing aircraft",
    2: "Quadrotor",
    3: "Coaxial helicopter",
    4: "Normal helicopter",
    5: "Ground installation",
    6: "Ground control station",
    7: "Airship",
    8: "Free balloon",
    9: "Rocket",
    10: "Ground rover",
    11: "Surface vessel",
    12: "Submarine",
    13: "Hexarotor",
    14: "Octorotor",
    15: "Tricopter",
    16: "Flapping wing",
    17: "Kite",
    18: "Companion computer",
    19: "Two-rotor VTOL",
    20: "Quad-rotor VTOL",
    21: "Tiltrotor VTOL",
    22: "VTOL with standard fixed wing configuration",
    23: "VTOL without tail sitters",
    24: "VTOL with dual rotors",
    25: "VTOL with three rotors",
    26: "VTOL with four rotors",
    27: "VTOL with five rotors",
    28: "VTOL with six rotors",
    29: "VTOL with seven rotors",
    30: "VTOL with eight rotors",
}

# MAV_AUTOPILOT values
MAV_AUTOPILOT = {
    0: "Generic",
    1: "Reserved",
    2: "ArduPilot",
    3: "OpenPilot",
    4: "AutoQuad",
    5: "AeroQuad",
    6: "PX4",
    7: "Sik",
    8: "Paparazzi",
    9: "UAV Dev Board",
    10: "ASLUAV",
    11: "SmartAP",
    12: "AirRails",
}

# from pymavlink import mavutil

# serial_port = "/dev/tty.usbmodem1103"
# baud_rate = 57600  # Common baud rate for ArduPilot

# master = mavutil.mavlink_connection(serial_port, baud=baud_rate)

# master.wait_heartbeat()
# print("Heartbeat received from system (system %u component %u)" % (master.target_system, master.target_component))

# master.mav.param_request_list_send(master.target_system, master.target_component)

# # Dictionary to hold parameters
# parameters = {}

# while True:
#     message = master.recv_match(type="PARAM_VALUE", blocking=True)
#     if message is not None:
#         param_id = message.param_id.strip("\x00")
#         param_value = message.param_value
#         parameters[param_id] = param_value
#         print(f"Parameter {param_id}: {param_value}")

#     # Optionally, break out of the loop after all parameters have been read
#     # Check if we have received all parameters
#     if message.param_index + 1 == message.param_count:
#         break

# print("All parameters received.")
