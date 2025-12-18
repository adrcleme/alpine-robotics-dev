#!/usr/bin/env python3
"""
Quick script to send basic failure mode 1 to ESP32.
"""

import socket
import time

# ESP32 Configuration
ESP32_IP = "192.168.1.10"
ESP32_PORT = 5005

def send_failure_mode1():
    """Send failure mode 1 command to ESP32."""
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Failure mode 1 parameters
    left_x = 0.0
    left_y = 0.0
    right_x = 0.0
    right_y = 0.0
    failure_mode_flag = 2
    left_wheel_velocity = 0.0
    right_wheel_velocity = 0.0
    
    # Format: joystick_axes, failure_mode_flag, left_wheel_vel, right_wheel_vel
    payload = (
        f"{left_x:.2f},{left_y:.2f},{right_x:.2f},{right_y:.2f},{failure_mode_flag},"
        f"{-left_wheel_velocity:.3f},{right_wheel_velocity:.3f}"
    )
    
    print(f"Sending failure mode 1 to {ESP32_IP}:{ESP32_PORT}")
    print(f"Payload: {payload}")
    
    try:
        sock.sendto(payload.encode(), (ESP32_IP, ESP32_PORT))
        print("Command sent successfully!")
    except Exception as e:
        print(f"Error sending command: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    send_failure_mode1()

