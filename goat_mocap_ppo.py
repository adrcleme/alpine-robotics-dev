import pygame
import socket
import asyncio
from datetime import datetime
import pandas as pd
import os
from mocap_client import MocapClient
from ppo_controller import PPOController
from navigation_utils import (
    load_waypoints_from_yaml,
    compute_heading_error,
    compute_distance,
    update_waypoint_index,
    wrap_to_pi
)
from archive.controller_debug_screen import ControllerDebugScreen
import threading
import numpy as np
import yaml
import traceback
import argparse
import math
import sys
import queue
traceback.print_exc() # print the traceback for the error


# Argparse
parser = argparse.ArgumentParser(description='Goat Recovery Controller')
# verbose flag
parser.add_argument('--verbose', action='store_true', help='Print debug information.')
parser.add_argument('--debug-screen', action='store_true', help='Show visual debug screen for controller inputs.')
args = parser.parse_args()
VERBOSE = args.verbose
DEBUG_SCREEN_ENABLED = args.debug_screen

# Global variables
# UDP Configuration
ESP32_IP = "192.168.1.10"  # Replace with your ESP32's IP, when connected to the SycamoreNet 17
ESP32_PORT = 5005
MOCAP_IP = '192.168.1.5' # .18
PORT = 9091
PREDICTION_DT = 0.045
TRACK_WIDTH = 0.35
DISTANCE_TARGET_REACHED = 0.75  # meters

# Model and waypoint configuration
RL_MODEL_PATH = os.getenv(
    "RL_POLICY_PATH",
    os.path.join(os.path.dirname(__file__), "latest.zip"),
)
WAYPOINT_CONFIG_PATH = os.getenv(
    "WAYPOINT_CONFIG_PATH",
    os.path.join(os.path.dirname(__file__), "waypoints.yaml"),
)
WAYPOINT_TERRAIN = os.getenv("WAYPOINT_TERRAIN", "default")

# Control mode
PPO_CONTROL_ACTIVE = False
# Terminal input queue for non-blocking input
input_queue = queue.Queue()
shutdown_flag = False

# Debug screen instance (if enabled)
debug_screen_instance = None

# Global state
mocap_client = None
ppo_controller = None
joystick = None  # Global joystick object
forward_vel_cmd = 0.0
steering_vel_cmd = 0.0
left_wheel_velocity = 0.0
right_wheel_velocity = 0.0
# Raw NN output values (before clipping)
nn_v_left = 0.0
nn_v_right = 0.0
nn_v_linear = 0.0
nn_v_angular = 0.0
ps4_data_log = []
data_log = []
mocap_velocity = 0.0
mocap_x = 0.0
mocap_y = 0.0
mocap_z = 0.0
failure_mode = 0
failure_mode_flag = 0
SAVE_DATA = True

# Waypoint management
waypoint_list = []
waypoint_list_xy = []  # Waypoints in mocap coordinates (x, y) - absolute coordinates
current_waypoint_idx = 0
all_waypoints_reached = False  # Flag to track if all waypoints have been completed
run_folder = None  # Folder for saving data files


"""PPO-controlled robot navigation system for the GOAT.
- Mocap readings for position
- IMU data for heading
- PPO neural network for control
- Waypoint following
- Terminal-based control menu (no controller required for state control)"""

"""Main functions and loop"""
# gamepad, sensor, export and cleanup functions

def input_reader_thread():
    """Thread function to read terminal input non-blocking."""
    while not shutdown_flag:
        try:
            line = sys.stdin.readline()
            if line:
                input_queue.put(line.strip())
        except:
            break

async def terminal_menu_loop():
    """Interactive terminal menu for controlling robot states."""
    global PPO_CONTROL_ACTIVE
    global failure_mode_flag
    global left_wheel_velocity
    global right_wheel_velocity
    global shutdown_flag
    global all_waypoints_reached
    global current_waypoint_idx
    
    # Start input reader thread
    input_thread = threading.Thread(target=input_reader_thread, daemon=True)
    input_thread.start()
    
    last_status_time = datetime.now()
    STATUS_UPDATE_INTERVAL = 2.0  # Show status every 2 seconds
    
    def print_menu():
        """Print the control menu."""
        global all_waypoints_reached, current_waypoint_idx, waypoint_list_xy
        print("\n" + "="*50)
        print("=== GOAT Control Menu ===")
        print("="*50)
        print(f"Current Status:")
        print(f"  PPO Control: {'ON' if PPO_CONTROL_ACTIVE else 'OFF'}")
        print(f"  Failure Mode: {failure_mode_flag}")
        print(f"  Wheel Velocities: L={left_wheel_velocity:.3f}, R={right_wheel_velocity:.3f}")
        if waypoint_list_xy:
            waypoint_status = f"Waypoint {current_waypoint_idx + 1}/{len(waypoint_list_xy)}"
            if all_waypoints_reached:
                waypoint_status += " (ALL REACHED - STOPPED)"
            print(f"  {waypoint_status}")
        print("\nCommands:")
        print("  1 / ppo    - Toggle PPO control")
        print("  2 / f1     - Set failure mode 1")
        print("  3 / f2     - Set failure mode 2")
        print("  4 / stop   - Emergency stop")
        print("  5 / status - Show status")
        print("  6 / help   - Show this menu")
        print("  q / quit   - Exit program")
        print("="*50)
        print("Enter command: ", end="", flush=True)
    
    print_menu()
    
    while not shutdown_flag:
        try:
            # Check for input
            try:
                command = input_queue.get_nowait().lower()
                
                if command in ['1', 'ppo']:
                    PPO_CONTROL_ACTIVE = not PPO_CONTROL_ACTIVE
                    mode = "ON" if PPO_CONTROL_ACTIVE else "OFF"
                    print(f"\n[Terminal] PPO control toggled {mode}")
                    if PPO_CONTROL_ACTIVE:
                        failure_mode_flag = 9  # Reset failure mode when PPO is active
                        all_waypoints_reached = False  # Reset waypoint completion flag
                        current_waypoint_idx = 0  # Reset to first waypoint
                        print(f"[Terminal] Waypoint mission reset to start")
                    print_menu()
                    
                elif command in ['2', 'f1', 'failure1']:
                    failure_mode_flag = 1
                    PPO_CONTROL_ACTIVE = False
                    left_wheel_velocity = 0.0
                    right_wheel_velocity = 0.0
                    print("\n[Terminal] Failure mode 1 activated")
                    print_menu()
                    
                elif command in ['3', 'f2', 'failure2']:
                    failure_mode_flag = 2
                    PPO_CONTROL_ACTIVE = False
                    left_wheel_velocity = 0.0
                    right_wheel_velocity = 0.0
                    print("\n[Terminal] Failure mode 2 activated")
                    print_menu()
                    
                elif command in ['4', 'stop']:
                    failure_mode_flag = 0
                    PPO_CONTROL_ACTIVE = False
                    left_wheel_velocity = 0.0
                    right_wheel_velocity = 0.0
                    print("\n[Terminal] Emergency stop activated")
                    print_menu()
                    
                elif command in ['5', 'status']:
                    print_menu()
                    
                elif command in ['6', 'help']:
                    print_menu()
                    
                elif command in ['q', 'quit', 'exit']:
                    print("\n[Terminal] Shutting down...")
                    shutdown_flag = True
                    break
                    
                else:
                    print(f"\n[Terminal] Unknown command: {command}. Type 'help' for options.")
                    print("Enter command: ", end="", flush=True)
                    
            except queue.Empty:
                pass
            
            # Periodically show status
            current_time = datetime.now()
            if (current_time - last_status_time).total_seconds() >= STATUS_UPDATE_INTERVAL:
                # Only show status if no recent command
                last_status_time = current_time
            
            await asyncio.sleep(0.1)  # Small delay to avoid tight loop
            
        except Exception as e:
            print(f"[Terminal Menu] ERROR: {e}")
            traceback.print_exc()
            await asyncio.sleep(0.1)

async def send_commands():
    """
    Send commands to robot (either from PPO or stopped when PPO is off).
    Handles command transmission.
    """
    global ps4_data_log
    global failure_mode_flag
    global PPO_CONTROL_ACTIVE
    global left_wheel_velocity
    global right_wheel_velocity
    global shutdown_flag
    
    while not shutdown_flag:
        # Read joystick axes if joystick is available (for data logging only)
        left_x = 0.0
        left_y = 0.0
        right_x = 0.0
        right_y = 0.0
        buttons = ["0"] * 16
        
        if joystick is not None:
            try:
                pygame.event.pump()  # Process events
                left_x = joystick.get_axis(0)  # Left stick X-axis
                left_y = joystick.get_axis(1)  # Left stick Y-axis
                right_x = joystick.get_axis(2)  # Right stick X-axis
                right_y = joystick.get_axis(3)  # Right stick Y-axis
                buttons = [str(joystick.get_button(i)) for i in range(joystick.get_numbuttons())]
            except:
                pass  # Joystick not available or disconnected
        
        # When PPO is off, ensure velocities are zero (no manual control)
        if not PPO_CONTROL_ACTIVE:
            if failure_mode_flag != 0:
                left_wheel_velocity = 0.0
                right_wheel_velocity = 0.0
            # Keep failure_mode_flag as set by terminal menu
        
        # When PPO is active, reset failure mode flag
        if PPO_CONTROL_ACTIVE:
            failure_mode_flag = 9  # Reset failure mode flag when PPO is active
        
        # Send commands to ESP32
        # Format: joystick_axes, failure_mode_flag, left_wheel_vel, right_wheel_vel
        payload = (
            f"{left_x:.2f},{left_y:.2f},{right_x:.2f},{right_y:.2f},{failure_mode_flag},"
            f"{-left_wheel_velocity:.3f},{right_wheel_velocity:.3f}"
        )
        #print(f"[COMMAND SENT] {payload}")
        sock.sendto(payload.encode(), (ESP32_IP, ESP32_PORT))
        
        ps4_data_log = [f"{left_x:.2f}", f"{left_y:.2f}", f"{right_x:.2f}", f"{right_y:.2f}"] + buttons
        await asyncio.sleep(PREDICTION_DT)  # Maintain ~20Hz loop as a debounce mechanism & avoid tight loop


async def ppo_control_loop():
    """
    Main control loop: receives sensor data, computes navigation inputs,
    updates PPO controller buffers, and generates commands.
    """
    global forward_vel_cmd
    global steering_vel_cmd
    global mocap_velocity
    global mocap_x
    global mocap_y
    global mocap_z
    global left_wheel_velocity
    global right_wheel_velocity
    global nn_v_left
    global nn_v_right
    global nn_v_linear
    global nn_v_angular
    global current_waypoint_idx
    global waypoint_list_xy
    global all_waypoints_reached
    global PPO_CONTROL_ACTIVE
    global failure_mode_flag
    global mocap_client
    global ppo_controller
    global shutdown_flag
    
    loop = asyncio.get_running_loop()
    
    while not shutdown_flag:
        try:
            t_before = datetime.now()
            sensor_packet, _ = await loop.run_in_executor(None, sock.recvfrom, 1024)
            sensor_data = sensor_packet.decode()

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            sensor_values = sensor_data.split(",")
            ps4_values = ps4_data_log if ps4_data_log else ["0.00", "0.00", "0.00", "0.00"] + ["0"] * 16
            
            # Extract commands from sensor data (first two values)
            # Sensor format: forward_vel_cmd, steering_vel_cmd, power_mW, current_mA, 
            #                busVoltage_V, shuntVoltage_mV, energy, charge, dieTemp
            try:
                forward_vel_cmd = float(sensor_values[0])
                steering_vel_cmd = float(sensor_values[1])
            except (ValueError, IndexError):
                forward_vel_cmd = 0.0
                steering_vel_cmd = 0.0

            # Get all mocap data
            mocap_velocity = mocap_client.get_last_velocity()
            mocap_x, mocap_y = mocap_client.get_last_position()
            mocap_z = mocap_client.get_last_z()
            
            # Extract heading from mocap (already converted from quaternion)
            try:
                mocap_heading = mocap_client.get_last_heading()
                # Wrap heading to [-pi, pi] to ensure consistent range for error computation
                current_heading_rad = wrap_to_pi(mocap_heading)
            except Exception:
                mocap_heading = 0.0
                current_heading_rad = 0.0
                if VERBOSE:
                    print("[PPO Control] Could not extract heading from mocap data")

            # Skip if no waypoints loaded
            if not waypoint_list_xy:
                await asyncio.sleep(PREDICTION_DT)
                continue

            # Use absolute mocap coordinates directly
            current_position = (mocap_x, mocap_y)
            target_waypoint = waypoint_list_xy[current_waypoint_idx]
            
            # Update waypoint index if reached
            distance_to_target = compute_distance(current_position, target_waypoint)
            if distance_to_target < DISTANCE_TARGET_REACHED:
                # Check if this is the last waypoint
                if current_waypoint_idx == len(waypoint_list_xy) - 1:
                    # All waypoints reached - stop the robot (same as pressing '4')
                    all_waypoints_reached = True
                    PPO_CONTROL_ACTIVE = False
                    left_wheel_velocity = 0.0
                    right_wheel_velocity = 0.0
                    failure_mode_flag = 0
                    if VERBOSE:
                        print(f"[PPO Control] All waypoints reached! Stopping robot.")
                else:
                    # Advance to next waypoint
                    current_waypoint_idx += 1
                    target_waypoint = waypoint_list_xy[current_waypoint_idx]
                    if VERBOSE:
                        print(f"[PPO Control] Advancing to waypoint {current_waypoint_idx} at ({target_waypoint[0]:.2f}, {target_waypoint[1]:.2f})")
                    distance_to_target = compute_distance(current_position, target_waypoint)

            # Compute heading error using absolute coordinates
            heading_error_rad = compute_heading_error(current_position, target_waypoint, current_heading_rad)

            # Update PPO controller buffers with absolute coordinates
            if ppo_controller is not None:
                ppo_controller.update_buffers(
                    current_position,
                    heading_error_rad,
                    distance_to_target,
                    target_waypoint
                )

            # Compute PPO command if control is active and waypoints not all reached
            if PPO_CONTROL_ACTIVE and ppo_controller is not None and not all_waypoints_reached:
                action = ppo_controller.compute_command()
                if action is not None:
                    v_left, v_right, v_linear, v_angular = action
                    # Store raw NN outputs before clipping
                    nn_v_left = v_left
                    nn_v_right = v_right
                    nn_v_linear = v_linear
                    nn_v_angular = v_angular
                    # Clip wheel velocities to [-1, 1] range
                    left_wheel_velocity = np.clip(v_left, -1.0, 1.0)
                    right_wheel_velocity = np.clip(v_right, -1.0, 1.0)
                    if VERBOSE:
                        print(f"[PPO Control] Command: left={left_wheel_velocity:.3f}, right={right_wheel_velocity:.3f}")
            else:
                # Reset NN outputs when PPO is not active
                nn_v_left = 0.0
                nn_v_right = 0.0
                nn_v_linear = 0.0
                nn_v_angular = 0.0

            # Log data
            data_log.append([
                timestamp
            ] + sensor_values + ps4_values + [
                # All mocap data with mocap_ prefix
                str(mocap_velocity), str(mocap_x), str(mocap_y), str(mocap_z),
                str(mocap_heading),
                forward_vel_cmd, steering_vel_cmd,
                left_wheel_velocity, right_wheel_velocity,
                # Raw NN outputs (before clipping)
                nn_v_left, nn_v_right, nn_v_linear, nn_v_angular,
                1.0 if PPO_CONTROL_ACTIVE else 0.0,
                heading_error_rad, current_heading_rad, distance_to_target,
                target_waypoint[0], target_waypoint[1],
                current_waypoint_idx
            ])

            await asyncio.sleep(PREDICTION_DT)
            t_now = datetime.now()
            dt = (t_now - t_before).total_seconds()
            if VERBOSE:
                print(f"[PPO Control] Loop dt: {dt:.4f}s")
                
        except BlockingIOError:
            pass  # No data received yet
        except Exception as e:
            print(f"[PPO Control] ERROR: {e}")
            traceback.print_exc()

async def save_to_csv():
    """Periodically saves joystick & IMU data to an Excel file."""
    global shutdown_flag
    SAVE_INTERVAL = 5.0  # Save every 5 seconds
    print("Data saving is always active.")
    last_save_time = datetime.now()
    
    while not shutdown_flag:  # data recording loop
        current_time = datetime.now()
        time_since_last_save = (current_time - last_save_time).total_seconds()
        
        # Save data periodically if there's data to save
        if time_since_last_save >= SAVE_INTERVAL and data_log:
            num_buttons = joystick.get_numbuttons() if joystick is not None else 16
            button_labels = [f"Button_{i}" for i in range(num_buttons)]
            # Sensor format: forward_vel_cmd, steering_vel_cmd, power_mW, current_mA, 
            #                busVoltage_V, shuntVoltage_mV, energy, charge, dieTemp
            header = ["Timestamp", 
                      "forward_vel_cmd", "steering_vel_cmd",
                      "power_mW", "current_mA", "busVoltage_V", "shuntVoltage_mV",
                      "energy", "charge", "dieTemp",
                      "Left_Stick_X", "Left_Stick_Y", "Right_Stick_X", "Right_Stick_Y"
                      ] + button_labels + [
                          # All mocap data received by mocap_client
                          "mocap_velocity", "mocap_x", "mocap_y", "mocap_z",
                          "mocap_heading",
                          "forward_vel_cmd", "steering_vel_cmd",
                          "left_wheel_vel", "right_wheel_vel",
                          # Raw NN outputs (before clipping)
                          "nn_v_left", "nn_v_right", "nn_v_linear", "nn_v_angular",
                          "ppo_control_active",
                          "heading_error_rad", "current_heading_rad", "distance_to_target",
                          "target_x", "target_y",
                          "current_waypoint_idx"
                      ]
            df = pd.DataFrame(data_log, columns=header)
            # Generate a new filename to batch save data
            filename = os.path.join(run_folder, f"{datetime.now().strftime('%H%M%S')}.csv")
            df.to_csv(filename, index=False)
            print(f"Data saved to {filename} ({len(data_log)} records), buffer cleared.")
            data_log.clear()  # Clear log after saving
            last_save_time = current_time
        
        await asyncio.sleep(0.05)  # Avoid tight loop
        

async def cleanup():
    """Handles cleanup on exit by saving data and closing resources."""
    global shutdown_flag
    global run_folder
    global mocap_client
    shutdown_flag = True
    
    # Save mocap client data if available
    if mocap_client is not None:
        try:
            mocap_filename = os.path.join(run_folder, f"mocap_raw_{datetime.now().strftime('%H%M%S')}.csv")
            mocap_client.save_data(mocap_filename)
            print(f"Mocap raw data saved to {mocap_filename}")
        except Exception as e:
            print(f"[Cleanup] Warning: Could not save mocap data: {e}")
    
    if data_log:
        print("\nSaving final data before exit...")
        num_buttons = joystick.get_numbuttons() if joystick is not None else 16
        button_labels = [f"Button_{i}" for i in range(num_buttons)]
        # Sensor format: forward_vel_cmd, steering_vel_cmd, power_mW, current_mA, 
        #                busVoltage_V, shuntVoltage_mV, energy, charge, dieTemp
        header = ["Timestamp", 
                  "forward_vel_cmd", "steering_vel_cmd",
                  "power_mW", "current_mA", "busVoltage_V", "shuntVoltage_mV",
                  "energy", "charge", "dieTemp",
                  "Left_Stick_X", "Left_Stick_Y", "Right_Stick_X", "Right_Stick_Y"
                  ] + button_labels + [
                      # All mocap data received by mocap_client
                      "mocap_velocity", "mocap_x", "mocap_y", "mocap_z",
                      "mocap_heading",
                      "forward_vel_cmd", "steering_vel_cmd",
                      "left_wheel_vel", "right_wheel_vel",
                      # Raw NN outputs (before clipping)
                      "nn_v_left", "nn_v_right", "nn_v_linear", "nn_v_angular",
                      "ppo_control_active",
                      "heading_error_rad", "current_heading_rad", "distance_to_target",
                      "target_x", "target_y",
                      "current_waypoint_idx"
                  ]
        df = pd.DataFrame(data_log, columns=header)
        filename = os.path.join(run_folder, f"{datetime.now().strftime('%H%M%S')}.csv")
        df.to_csv(filename, index=False)
        print(f"Final data saved to {filename}")

    sock.close()
    pygame.quit()
    print("Cleanup complete. Exiting.")

async def main():
    """Runs all tasks concurrently."""
    global shutdown_flag
    tasks = [send_commands(), ppo_control_loop(), save_to_csv(), terminal_menu_loop()]
    
    # Add debug screen task if enabled
    if DEBUG_SCREEN_ENABLED and debug_screen_instance is not None and joystick is not None:
        tasks.append(debug_screen_instance.update_loop(joystick))
    
    try:
        await asyncio.gather(*tasks)
    except Exception as e:
        print(f"[Main] Error in main loop: {e}")
        traceback.print_exc()
    finally:
        if shutdown_flag:
            await cleanup()

"""run program"""
if __name__ == "__main__":
    try:
        """Perform initial setup tasks"""
        run_folder = datetime.now().strftime('%Y_%m_%d_%H%M%S_goat')
        os.makedirs(run_folder, exist_ok=True)

        # Load waypoints
        try:
            waypoint_list, spacing_override, yaml_target_lat, yaml_target_lon = load_waypoints_from_yaml(
                WAYPOINT_CONFIG_PATH, WAYPOINT_TERRAIN
            )
            # Convert waypoints to mocap coordinates (assuming mocap uses same coordinate system)
            # If waypoints are in lat/lon, you may need coordinate transformation
            # For now, assuming waypoints are already in mocap (x, y) format
            waypoint_list_xy = [(float(wp[0]), float(wp[1])) for wp in waypoint_list]
            print(f"[Init] Loaded {len(waypoint_list_xy)} waypoints from {WAYPOINT_CONFIG_PATH}")
        except Exception as err:
            print(f"[Init] Warning: Failed to load waypoints: {err}")
            print("[Init] Continuing without waypoints - you can set them manually")
            waypoint_list_xy = []

        # Initialize the Mocap client
        mocap_client = MocapClient(MOCAP_IP, PORT)
        # Start the thread for the mocap client
        mocap_thread = threading.Thread(target=mocap_client.listen, daemon=True)
        mocap_thread.start()
        print(f"[Init] Mocap client launched on {MOCAP_IP}:{PORT}")

        # Initialize UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", ESP32_PORT))  # Listen for IMU data
        sock.setblocking(False)  # Set non-blocking mode
        print(f"[Init] UDP socket bound to port {ESP32_PORT}")
        
        # Load PPO model
        print(f"[Init] Loading PPO model from {RL_MODEL_PATH}...")
        ppo_controller = PPOController(RL_MODEL_PATH, track_width=TRACK_WIDTH)
        if ppo_controller.model is None:
            print("[Init] Warning: PPO model not loaded. PPO control will be unavailable.")
        else:
            print("[Init] PPO model loaded successfully")
        
        # Initialize pygame and joystick (optional - for data logging only)
        pygame.init()
        pygame.joystick.init()

        if pygame.joystick.get_count() == 0:
            print("[Init] No controller detected. Continuing without joystick (data logging will use zeros).")
            joystick = None
        else:
            # Initialize joystick (module-level variable, no global needed here)
            joystick = pygame.joystick.Joystick(0)
            joystick.init()
            print(f"[Init] Connected to {joystick.get_name()} (for data logging only)")
        
        print("[Init] Control is now terminal-based. Use the menu to control robot states.")
        
        # Initialize debug screen if enabled
        if DEBUG_SCREEN_ENABLED:
            debug_screen_instance = ControllerDebugScreen()
            if debug_screen_instance.initialize():
                print("[Init] Debug screen enabled - visual controller display active")
            else:
                print("[Init] Warning: Could not create debug screen. Continuing without debug screen...")
                debug_screen_instance = None

        input("[Init] Press ENTER to start...")
        
        # Generate a unique filename for this test run
        filename = os.path.join(run_folder, f"{datetime.now().strftime('%H%M%S')}.csv")
        asyncio.run(main())
        
    except KeyboardInterrupt:
        print("\n[Exit] Cleaning up...")
        asyncio.run(cleanup())
        print("[Exit] Program exited.")
    except Exception as e:
        print(f"\n[Exit] Unexpected error: {e}")
        traceback.print_exc()
        try:
            asyncio.run(cleanup())
        except Exception:
            pass

        