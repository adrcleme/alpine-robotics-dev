#!/usr/bin/env python3
"""
Test script to verify PS4 controller connection and input reading.
Inspired by goat_mocap_ppo.py controller logic.
"""

import pygame
import sys
import time
import os

# Button mappings - NOTE: These may vary on macOS!
# Standard PS4 mapping (may differ on your system):
#   0: X (bottom button)
#   1: Circle/O (right button)  
#   2: Triangle (top button)
#   3: Square (left button)
#   4: L1, 5: R1, 6: L2, 7: R2
#   8: Share, 9: Options
#   10: L3, 11: R3
#   12: PS button, 13: Touchpad
# The screen shows "Name (Index)" - verify the physical button matches the name!
PPO_TOGGLE_BUTTON = 8  # Right stick press
BUTTON_NAMES = {
    0: "Cross",
    1: "Circle",
    2: "Square",
    3: "Triangle",
    4: "Share Button", # Do not use this button for other purposes.
    5: "PS Button", # Do not use this button for other purposes.
    6: "Options Button", # Do not use this button for other purposes. (disconnect the controller)
    7: "L. Stick Press",
    8: "R. Stick Press",
    9: "L1",
    10: "R1",
    11: "Up",
    12: "Down",
    13: "Left",
    14 : "Right",
    15 : 'Touch Pad Click',
}

AXIS_NAMES = {
    0: "Left Stick X",
    1: "Left Stick Y",
    2: "Right Stick X",
    3: "Right Stick Y",
    4: "L2 Trigger",
    5: "R2 Trigger"
}

AXIS_THRESHOLD = 0.01  # Minimum change to report axis movement

# Button functions in goat_mocap_ppo.py
BUTTON_FUNCTIONS = {
    0: "Failure Mode 1",
    1: "Failure Mode 2",
    3: "EMERGENCY STOP",
    8: "Toggle PPO",
    9: "Stop Save Data",
    10: "Start Save Data",
}

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (128, 128, 128)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
DARK_GRAY = (64, 64, 64)
LIGHT_GRAY = (192, 192, 192)


def draw_debug_screen(screen, joystick, font, small_font, frame_count=0):
    """Draw the visual debug screen showing all controller inputs."""
    screen.fill(BLACK)
    
    # Title bar
    title = font.render("PS4 Controller Debug Screen", True, WHITE)
    screen.blit(title, (20, 10))
    
    controller_name = small_font.render(f"Controller: {joystick.get_name()}", True, LIGHT_GRAY)
    screen.blit(controller_name, (20, 45))
    
    # Status indicator (shows the screen is updating)
    status_text = small_font.render(f"Status: Active | Frame: {frame_count}", True, GREEN)
    screen.blit(status_text, (20, 70))
    
    # Two-column layout: Buttons on left, Axes/Hats on right
    left_col_x = 20
    right_col_x = 720  # Start right column after buttons
    start_y = 80
    
    # ========== LEFT COLUMN: BUTTONS ==========
    button_title = font.render("BUTTONS", True, WHITE)
    screen.blit(button_title, (left_col_x, start_y))
    
    button_y_start = start_y + 35
    button_width = 130
    button_height = 28
    button_spacing = 8
    function_x_offset = button_width + 8
    column_spacing = 180  # Space between the two columns
    
    num_buttons = joystick.get_numbuttons()
    
    # Column 1 positions (buttons 0-8)
    col1_x = left_col_x
    col1_y = button_y_start
    
    # Column 2 positions (buttons 9+)
    col2_x = left_col_x + button_width + column_spacing
    col2_y = button_y_start
    
    # Draw buttons in 2 vertical columns
    for i in range(num_buttons):
        button_state = joystick.get_button(i)
        button_name = BUTTON_NAMES.get(i, f"Btn {i}")
        button_function = BUTTON_FUNCTIONS.get(i, "")
        
        # Determine which column: 0-8 in left, 9+ in right
        if i <= 8:  # Buttons 0-8 go to column 1 (left)
            button_x = col1_x
            button_y = col1_y
            # Move column 1 down for next button
            col1_y += button_height + button_spacing
        else:  # Buttons 9+ go to column 2 (right)
            button_x = col2_x
            button_y = col2_y
            # Move column 2 down for next button
            col2_y += button_height + button_spacing
        
        # Color: green if pressed, dark gray if not
        bg_color = GREEN if button_state else DARK_GRAY
        text_color = BLACK if button_state else WHITE
        
        # Draw button rectangle
        pygame.draw.rect(screen, bg_color, (button_x, button_y, button_width, button_height))
        pygame.draw.rect(screen, WHITE, (button_x, button_y, button_width, button_height), 1)
        
        # Draw button name and index (compact)
        display_text = f"{button_name} ({i})"
        button_text = small_font.render(display_text, True, text_color)
        text_rect = button_text.get_rect(center=(button_x + button_width//2, button_y + button_height//2))
        screen.blit(button_text, text_rect)
        
        # Draw function label on the right (if it has a function)
        if button_function:
            func_color = RED if i == 3 else LIGHT_GRAY
            function_text = small_font.render(f"→ {button_function}", True, func_color)
            screen.blit(function_text, (button_x + function_x_offset, button_y + 4))
    
    # ========== RIGHT COLUMN: AXES ==========
    axis_title = font.render("AXES", True, WHITE)
    screen.blit(axis_title, (right_col_x, start_y))
    
    axis_y = start_y + 35
    bar_width = 350
    bar_height = 22
    bar_spacing = 30
    
    for i in range(joystick.get_numaxes()):
        axis_value = joystick.get_axis(i)
        axis_name = AXIS_NAMES.get(i, f"Axis {i}")
        
        # Draw axis label
        axis_label = small_font.render(f"{axis_name}:", True, WHITE)
        screen.blit(axis_label, (right_col_x, axis_y))
        
        # Draw background bar
        bar_x = right_col_x + 120
        bar_y = axis_y
        pygame.draw.rect(screen, DARK_GRAY, (bar_x, bar_y, bar_width, bar_height))
        pygame.draw.rect(screen, WHITE, (bar_x, bar_y, bar_width, bar_height), 1)
        
        # Draw center line
        center_x = bar_x + bar_width // 2
        pygame.draw.line(screen, GRAY, (center_x, bar_y), (center_x, bar_y + bar_height), 1)
        
        # Draw filled bar
        fill_color = GREEN if abs(axis_value) > 0.1 else DARK_GRAY
        half_bar = bar_width // 2
        
        if axis_value > 0:
            fill_x = center_x
            fill_width_actual = int(axis_value * half_bar)
            pygame.draw.rect(screen, fill_color, (fill_x, bar_y, fill_width_actual, bar_height))
        elif axis_value < 0:
            fill_width_actual = int(abs(axis_value) * half_bar)
            fill_x = center_x - fill_width_actual
            pygame.draw.rect(screen, fill_color, (fill_x, bar_y, fill_width_actual, bar_height))
        
        # Draw value text
        value_text = small_font.render(f"{axis_value:6.3f}", True, WHITE)
        screen.blit(value_text, (bar_x + bar_width + 8, bar_y))
        
        axis_y += bar_spacing
    
    # ========== RIGHT COLUMN: HATS (D-PAD) ==========
    if joystick.get_numhats() > 0:
        hat_y = axis_y + 10
        hat_title = font.render("D-PAD", True, WHITE)
        screen.blit(hat_title, (right_col_x, hat_y))
        hat_y += 30
        
        for i in range(joystick.get_numhats()):
            hat_value = joystick.get_hat(i)
            hat_text = small_font.render(f"Hat {i}: {hat_value}", True, WHITE)
            screen.blit(hat_text, (right_col_x, hat_y))
            hat_y += 25
    
    # ========== BOTTOM: INSTRUCTIONS ==========
    instructions_y = 460
    instructions = [
        "Press 'Q' to quit  |  Green = pressed  |  Red = Emergency Stop"
    ]
    for instruction in instructions:
        inst_text = small_font.render(instruction, True, LIGHT_GRAY)
        screen.blit(inst_text, (20, instructions_y))
    
    pygame.display.flip()


def print_controller_info(joystick):
    """Print controller information."""
    print("\n" + "="*60)
    print(f"Controller Name: {joystick.get_name()}")
    print(f"Number of Axes: {joystick.get_numaxes()}")
    print(f"Number of Buttons: {joystick.get_numbuttons()}")
    print(f"Number of Hats: {joystick.get_numhats()}")
    print("="*60 + "\n")


def main():
    """Main test loop."""
    print("Initializing pygame...")
    print("[INFO] On macOS: If controller isn't detected, check System Settings > Privacy & Security > Accessibility")
    print("      and ensure Terminal/Python has accessibility permissions.\n")
    
    pygame.init()
    pygame.joystick.init()
    
    # Create a visual debug screen window
    WINDOW_WIDTH = 1400
    WINDOW_HEIGHT = 500
    try:
        screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("PS4 Controller Debug Screen")
        print("[INFO] Visual debug screen created")
    except Exception as e:
        print(f"[ERROR] Could not create display window: {e}")
        sys.exit(1)
    
    # Initialize fonts
    try:
        font = pygame.font.Font(None, 36)
        small_font = pygame.font.Font(None, 24)
    except:
        font = pygame.font.SysFont('arial', 36)
        small_font = pygame.font.SysFont('arial', 24)
    
    # Check for controllers
    if pygame.joystick.get_count() == 0:
        print("[ERROR] No controller detected!")
        print("Make sure your PS4 controller is connected via Bluetooth.")
        print("[TROUBLESHOOTING]")
        print("  1. Check System Settings > Privacy & Security > Accessibility")
        print("  2. Ensure Terminal (or your IDE) has accessibility permissions")
        print("  3. Try disconnecting and reconnecting the controller")
        print("  4. Check if controller appears in System Settings > Bluetooth")
        sys.exit(1)
    
    print(f"[INFO] Found {pygame.joystick.get_count()} controller(s)")
    
    # Initialize first controller
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    
    print_controller_info(joystick)
    
    # Test if we can read button states immediately
    print("[DEBUG] Testing direct button read...")
    test_buttons = [joystick.get_button(i) for i in range(min(5, joystick.get_numbuttons()))]
    print(f"[DEBUG] First 5 button states: {test_buttons}")
    print("[DEBUG] If all False, try pressing a button now to verify connection...")
    
    print("\n[INFO] Visual debug screen will open.")
    print("[INFO] Press 'Q' or Square button to quit.")
    print("[INFO] All inputs will be displayed in real-time on screen.\n")
    
    # Track previous states
    prev_buttons = [False] * joystick.get_numbuttons()
    prev_axes = [0.0] * joystick.get_numaxes()
    prev_hats = [(0, 0)] * joystick.get_numhats()
    
    try:
        running = True
        clock = pygame.time.Clock()
        frame_count = 0
        last_update_time = time.time()
        
        print("[INFO] Debug screen active. Interact with your controller to see inputs!")
        
        while running:
            try:
                # CRITICAL: On macOS, pygame.event.pump() must be called to process joystick events
                pygame.event.pump()
                
                # Process window events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_q or event.key == pygame.K_ESCAPE:
                            running = False
                
                # Verify joystick is still valid and connected
                try:
                    # Check if joystick is still initialized
                    if pygame.joystick.get_count() == 0:
                        print("[ERROR] No controllers detected! Controller may have disconnected.")
                        print("[INFO] Please reconnect the controller and restart the script.")
                        running = False
                        break
                    
                    num_buttons = joystick.get_numbuttons()
                    num_axes = joystick.get_numaxes()
                    
                    # Ensure prev_arrays are the right size
                    if len(prev_buttons) != num_buttons:
                        prev_buttons = [False] * num_buttons
                    if len(prev_axes) != num_axes:
                        prev_axes = [0.0] * num_axes
                        
                except (pygame.error, AttributeError) as e:
                    print(f"[ERROR] Joystick connection lost: {e}")
                    print("[INFO] Controller may have disconnected. Exiting...")
                    running = False
                    break
                except Exception as e:
                    print(f"[WARNING] Unexpected error checking joystick: {e}")
                    # Continue anyway, might be recoverable
                
                # Update button states for visual display
                try:
                    for i in range(num_buttons):
                        prev_buttons[i] = joystick.get_button(i)
                except Exception as e:
                    print(f"[WARNING] Error reading buttons: {e}")
                
                # Update axis states for visual display
                try:
                    for i in range(num_axes):
                        prev_axes[i] = joystick.get_axis(i)
                except Exception as e:
                    print(f"[WARNING] Error reading axes: {e}")
                
                # Update hat states for visual display
                try:
                    for i in range(joystick.get_numhats()):
                        prev_hats[i] = joystick.get_hat(i)
                except Exception as e:
                    print(f"[WARNING] Error reading hats: {e}")
                
                # Draw the debug screen
                try:
                    draw_debug_screen(screen, joystick, font, small_font, frame_count)
                except Exception as e:
                    print(f"[ERROR] Error drawing debug screen: {e}")
                    import traceback
                    traceback.print_exc()
                
                # Check for quit button (Button 3 - Square)
                try:
                    if joystick.get_button(3):
                        running = False
                        break
                except:
                    pass  # Ignore errors when checking quit button
                
                # Control frame rate (60 FPS for smooth updates)
                clock.tick(60)
                
                # Debug: Print status every 60 seconds
                frame_count += 1
                current_time = time.time()
                if current_time - last_update_time >= 60.0:
                    print(f"[DEBUG] Still running - {frame_count} frames processed, {current_time - last_update_time:.1f}s elapsed")
                    last_update_time = current_time
                    # Verify joystick is still responding
                    try:
                        test_button = joystick.get_button(0)
                        print(f"[DEBUG] Joystick still responsive (button 0 = {test_button})")
                    except Exception as e:
                        print(f"[ERROR] Joystick no longer responsive: {e}")
                        running = False
                        break
                
            except Exception as e:
                print(f"[ERROR] Unexpected error in main loop: {e}")
                import traceback
                traceback.print_exc()
                # Continue running but log the error
                time.sleep(0.1)  # Small delay before retrying
            
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
    finally:
        pygame.quit()
        print("\n[INFO] Test complete. Controller disconnected.")


if __name__ == "__main__":
    main()

