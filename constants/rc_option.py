# Define the options as constants
RC_OPTION_NONE = 0
RC_OPTION_RETURN_TO_LAUNCH = 1
RC_OPTION_FLIGHT_MODE = 2
RC_OPTION_SAVE_TRIM = 4
RC_OPTION_SAVE_WP = 5
RC_OPTION_CAMERA_CONTROL = 6
RC_OPTION_CAMERA_TRIGGER = 9
RC_OPTION_RANGEFINDER = 10
RC_OPTION_GRIPPER = 12
RC_OPTION_PARACHUTE_RELEASE = 21
RC_OPTION_PARACHUTE_ENABLE = 22
RC_OPTION_PARACHUTE_DISABLE = 23
RC_OPTION_MOUNT_PAN_CONTROL = 24
RC_OPTION_MOUNT_TILT_CONTROL = 25
RC_OPTION_MOUNT_ROLL_CONTROL = 26
RC_OPTION_LANDING_GEAR = 29
RC_OPTION_TAKEOFF = 30
RC_OPTION_ACRO_TRAINER = 31
RC_OPTION_DO_JUMP = 32
RC_OPTION_DO_LAND_START = 33
RC_OPTION_DO_SET_ROI_LOCATION = 34
RC_OPTION_DO_SET_ROI_WPNEXT = 35
RC_OPTION_DO_SET_ROI_NONE = 36
RC_OPTION_DO_SET_ROI_SYSID = 37
RC_OPTION_DO_FLIGHTTERMINATION = 38
RC_OPTION_ARM_DISARM = 41
RC_OPTION_GIMBAL_RETRACT = 51
RC_OPTION_GIMBAL_NEUTRAL = 52
RC_OPTION_GIMBAL_RETRACT_NEUTRAL = 53
RC_OPTION_GIMBAL_CONTROL = 54
RC_OPTION_RC_OVERRIDE_ENABLE = 60
RC_OPTION_BRAKE = 65
RC_OPTION_AIRBRAKE = 66
RC_OPTION_AUTO_MISSION_PAUSE = 67
RC_OPTION_AVOIDANCE_ENABLE = 68
RC_OPTION_PRECISION_LAND = 69
RC_OPTION_AVOIDANCE_TYPE = 70
RC_OPTION_ARBITER_CONTROL = 71
RC_OPTION_PAYLOAD_CONTROL = 72
RC_OPTION_HOLD = 74
RC_OPTION_ADSB_AVOID = 75
RC_OPTION_AUTOTUNE_ENABLE = 76
RC_OPTION_ROLL_PITCH_AUTO_TUNE = 77
RC_OPTION_YAW_AUTO_TUNE = 78
RC_OPTION_PITCH_AUTO_TUNE = 79
RC_OPTION_ROLL_AUTO_TUNE = 80
RC_OPTION_THROTTLE_AUTO_TUNE = 81
RC_OPTION_THROTTLE_HOLD = 82
RC_OPTION_LAND = 84
RC_OPTION_LOITER = 85
RC_OPTION_ACRO = 86
RC_OPTION_GPS_SPEED_LIMIT = 87
RC_OPTION_RANGEFINDER_MODE = 88
RC_OPTION_RETURN_HOME = 89
RC_OPTION_DO_SET_HOME = 90
RC_OPTION_LOITER_TURN_MODE = 91
RC_OPTION_AUTO_TAKEOFF = 92
RC_OPTION_AUTO_LAND = 93
RC_OPTION_START_MISSION = 94
RC_OPTION_STOP_MISSION = 95
RC_OPTION_MISSION_RETRY = 96
RC_OPTION_MISSION_JUMP = 97
RC_OPTION_MISSION_RTL = 98
RC_OPTION_USER_1 = 100
RC_OPTION_USER_2 = 101
RC_OPTION_USER_3 = 102
RC_OPTION_USER_4 = 103
RC_OPTION_USER_5 = 104
RC_OPTION_USER_6 = 105
RC_OPTION_USER_7 = 106
RC_OPTION_USER_8 = 107
RC_OPTION_USER_9 = 108
RC_OPTION_USER_10 = 109

# Define the descriptions dictionary using the constants
RC_OPTION_DESCRIPTIONS = {
    RC_OPTION_NONE: "None",
    RC_OPTION_RETURN_TO_LAUNCH: "Return to Launch",
    RC_OPTION_FLIGHT_MODE: "Flight Mode",
    RC_OPTION_SAVE_TRIM: "Save Trim",
    RC_OPTION_SAVE_WP: "Save Waypoint",
    RC_OPTION_CAMERA_CONTROL: "Camera Control",
    RC_OPTION_CAMERA_TRIGGER: "Camera Trigger",
    RC_OPTION_RANGEFINDER: "Rangefinder",
    RC_OPTION_GRIPPER: "Gripper",
    RC_OPTION_PARACHUTE_RELEASE: "Parachute Release",
    RC_OPTION_PARACHUTE_ENABLE: "Parachute Enable",
    RC_OPTION_PARACHUTE_DISABLE: "Parachute Disable",
    RC_OPTION_MOUNT_PAN_CONTROL: "Mount Pan Control",
    RC_OPTION_MOUNT_TILT_CONTROL: "Mount Tilt Control",
    RC_OPTION_MOUNT_ROLL_CONTROL: "Mount Roll Control",
    RC_OPTION_LANDING_GEAR: "Landing Gear",
    RC_OPTION_TAKEOFF: "Takeoff",
    RC_OPTION_ACRO_TRAINER: "Acro Trainer",
    RC_OPTION_DO_JUMP: "Do Jump",
    RC_OPTION_DO_LAND_START: "Do Land Start",
    RC_OPTION_DO_SET_ROI_LOCATION: "Do Set ROI Location",
    RC_OPTION_DO_SET_ROI_WPNEXT: "Do Set ROI WPNext",
    RC_OPTION_DO_SET_ROI_NONE: "Do Set ROI None",
    RC_OPTION_DO_SET_ROI_SYSID: "Do Set ROI SysID",
    RC_OPTION_DO_FLIGHTTERMINATION: "Do Flight Termination",
    RC_OPTION_ARM_DISARM: "Arm/Disarm",
    RC_OPTION_GIMBAL_RETRACT: "Gimbal Retract",
    RC_OPTION_GIMBAL_NEUTRAL: "Gimbal Neutral",
    RC_OPTION_GIMBAL_RETRACT_NEUTRAL: "Gimbal Retract Neutral",
    RC_OPTION_GIMBAL_CONTROL: "Gimbal Control",
    RC_OPTION_RC_OVERRIDE_ENABLE: "RC Override Enable",
    RC_OPTION_BRAKE: "Brake",
    RC_OPTION_AIRBRAKE: "Airbrake",
    RC_OPTION_AUTO_MISSION_PAUSE: "Auto Mission Pause",
    RC_OPTION_AVOIDANCE_ENABLE: "Avoidance Enable",
    RC_OPTION_PRECISION_LAND: "Precision Land",
    RC_OPTION_AVOIDANCE_TYPE: "Avoidance Type",
    RC_OPTION_ARBITER_CONTROL: "Arbiter Control",
    RC_OPTION_PAYLOAD_CONTROL: "Payload Control",
    RC_OPTION_HOLD: "Hold",
    RC_OPTION_ADSB_AVOID: "ADSB Avoid",
    RC_OPTION_AUTOTUNE_ENABLE: "Autotune Enable",
    RC_OPTION_ROLL_PITCH_AUTO_TUNE: "Roll/Pitch Auto Tune",
    RC_OPTION_YAW_AUTO_TUNE: "Yaw Auto Tune",
    RC_OPTION_PITCH_AUTO_TUNE: "Pitch Auto Tune",
    RC_OPTION_ROLL_AUTO_TUNE: "Roll Auto Tune",
    RC_OPTION_THROTTLE_AUTO_TUNE: "Throttle Auto Tune",
    RC_OPTION_THROTTLE_HOLD: "Throttle Hold",
    RC_OPTION_LAND: "Land",
    RC_OPTION_LOITER: "Loiter",
    RC_OPTION_ACRO: "Acro",
    RC_OPTION_GPS_SPEED_LIMIT: "GPS Speed Limit",
    RC_OPTION_RANGEFINDER_MODE: "Rangefinder Mode",
    RC_OPTION_RETURN_HOME: "Return Home",
    RC_OPTION_DO_SET_HOME: "Do Set Home",
    RC_OPTION_LOITER_TURN_MODE: "Loiter Turn Mode",
    RC_OPTION_AUTO_TAKEOFF: "Auto Takeoff",
    RC_OPTION_AUTO_LAND: "Auto Land",
    RC_OPTION_START_MISSION: "Start Mission",
    RC_OPTION_STOP_MISSION: "Stop Mission",
    RC_OPTION_MISSION_RETRY: "Mission Retry",
    RC_OPTION_MISSION_JUMP: "Mission Jump",
    RC_OPTION_MISSION_RTL: "Mission RTL",
    RC_OPTION_USER_1: "User 1",
    RC_OPTION_USER_2: "User 2",
    RC_OPTION_USER_3: "User 3",
    RC_OPTION_USER_4: "User 4",
    RC_OPTION_USER_5: "User 5",
    RC_OPTION_USER_6: "User 6",
    RC_OPTION_USER_7: "User 7",
    RC_OPTION_USER_8: "User 8",
    RC_OPTION_USER_9: "User 9",
    RC_OPTION_USER_10: "User 10",
}
