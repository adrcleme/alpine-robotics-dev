"""
Controller Debug Screen Module
Provides visual debug screen for PS4 controller inputs.
"""

import pygame
import asyncio

# Debug screen configuration
DEBUG_SCREEN_WIDTH = 1400
DEBUG_SCREEN_HEIGHT = 500

# Button names for debug screen (matching your system's mapping)
BUTTON_NAMES = {
    0: "Cross",
    1: "Circle",
    2: "Square",
    3: "Triangle",
    4: "Share Button",
    5: "PS Button",
    6: "Options Button",
    7: "L. Stick Press",
    8: "R. Stick Press",
    9: "L1",
    10: "R1",
    11: "Up",
    12: "Down",
    13: "Left",
    14: "Right",
    15: 'Touch Pad Click',
}

AXIS_NAMES = {
    0: "Left Stick X",
    1: "Left Stick Y",
    2: "Right Stick X",
    3: "Right Stick Y",
    4: "L2 Trigger",
    5: "R2 Trigger"
}

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
DARK_GRAY = (64, 64, 64)
LIGHT_GRAY = (192, 192, 192)


class ControllerDebugScreen:
    """Manages the visual debug screen for controller inputs."""
    
    def __init__(self, width=DEBUG_SCREEN_WIDTH, height=DEBUG_SCREEN_HEIGHT):
        """Initialize the debug screen."""
        self.width = width
        self.height = height
        self.screen = None
        self.font = None
        self.small_font = None
        self.initialized = False
    
    def initialize(self):
        """Create the pygame display window and fonts."""
        try:
            self.screen = pygame.display.set_mode((self.width, self.height))
            pygame.display.set_caption("GOAT Controller Debug Screen")
            try:
                self.font = pygame.font.Font(None, 36)
                self.small_font = pygame.font.Font(None, 24)
            except:
                self.font = pygame.font.SysFont('arial', 36)
                self.small_font = pygame.font.SysFont('arial', 24)
            self.initialized = True
            return True
        except Exception as e:
            print(f"[Debug Screen] Warning: Could not create debug screen: {e}")
            return False
    
    def draw(self, joystick):
        """Draw the visual debug screen showing all controller inputs."""
        if not self.initialized or self.screen is None or joystick is None:
            return
        
        self.screen.fill(BLACK)
        
        # Title bar
        title = self.font.render("PS4 Controller Debug Screen", True, WHITE)
        self.screen.blit(title, (20, 10))
        
        controller_name = self.small_font.render(f"Controller: {joystick.get_name()}", True, LIGHT_GRAY)
        self.screen.blit(controller_name, (20, 45))
        
        # Two-column layout: Buttons on left, Axes/Hats on right
        left_col_x = 20
        right_col_x = 720
        start_y = 80
        
        # ========== LEFT COLUMN: BUTTONS ==========
        button_title = self.font.render("BUTTONS", True, WHITE)
        self.screen.blit(button_title, (left_col_x, start_y))
        
        button_y_start = start_y + 35
        button_width = 130
        button_height = 28
        button_spacing = 8
        function_x_offset = button_width + 8
        column_spacing = 180
        
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
            if i <= 8:
                button_x = col1_x
                button_y = col1_y
                col1_y += button_height + button_spacing
            else:
                button_x = col2_x
                button_y = col2_y
                col2_y += button_height + button_spacing
            
            # Color: green if pressed, dark gray if not
            bg_color = GREEN if button_state else DARK_GRAY
            text_color = BLACK if button_state else WHITE
            
            # Draw button rectangle
            pygame.draw.rect(self.screen, bg_color, (button_x, button_y, button_width, button_height))
            pygame.draw.rect(self.screen, WHITE, (button_x, button_y, button_width, button_height), 1)
            
            # Draw button name and index
            display_text = f"{button_name} ({i})"
            button_text = self.small_font.render(display_text, True, text_color)
            text_rect = button_text.get_rect(center=(button_x + button_width//2, button_y + button_height//2))
            self.screen.blit(button_text, text_rect)
            
            # Draw function label on the right (if it has a function)
            if button_function:
                func_color = RED if i == 3 else LIGHT_GRAY
                function_text = self.small_font.render(f"→ {button_function}", True, func_color)
                self.screen.blit(function_text, (button_x + function_x_offset, button_y + 4))
        
        # ========== RIGHT COLUMN: AXES ==========
        axis_title = self.font.render("AXES", True, WHITE)
        self.screen.blit(axis_title, (right_col_x, start_y))
        
        axis_y = start_y + 35
        bar_width = 350
        bar_height = 22
        bar_spacing = 30
        
        for i in range(joystick.get_numaxes()):
            axis_value = joystick.get_axis(i)
            axis_name = AXIS_NAMES.get(i, f"Axis {i}")
            
            # Draw axis label
            axis_label = self.small_font.render(f"{axis_name}:", True, WHITE)
            self.screen.blit(axis_label, (right_col_x, axis_y))
            
            # Draw background bar
            bar_x = right_col_x + 120
            bar_y = axis_y
            pygame.draw.rect(self.screen, DARK_GRAY, (bar_x, bar_y, bar_width, bar_height))
            pygame.draw.rect(self.screen, WHITE, (bar_x, bar_y, bar_width, bar_height), 1)
            
            # Draw center line
            center_x = bar_x + bar_width // 2
            pygame.draw.line(self.screen, GRAY, (center_x, bar_y), (center_x, bar_y + bar_height), 1)
            
            # Draw filled bar
            fill_color = GREEN if abs(axis_value) > 0.1 else DARK_GRAY
            half_bar = bar_width // 2
            
            if axis_value > 0:
                fill_x = center_x
                fill_width_actual = int(axis_value * half_bar)
                pygame.draw.rect(self.screen, fill_color, (fill_x, bar_y, fill_width_actual, bar_height))
            elif axis_value < 0:
                fill_width_actual = int(abs(axis_value) * half_bar)
                fill_x = center_x - fill_width_actual
                pygame.draw.rect(self.screen, fill_color, (fill_x, bar_y, fill_width_actual, bar_height))
            
            # Draw value text
            value_text = self.small_font.render(f"{axis_value:6.3f}", True, WHITE)
            self.screen.blit(value_text, (bar_x + bar_width + 8, axis_y))
            
            axis_y += bar_spacing
        
        # ========== RIGHT COLUMN: HATS (D-PAD) ==========
        if joystick.get_numhats() > 0:
            hat_y = axis_y + 10
            hat_title = self.font.render("D-PAD", True, WHITE)
            self.screen.blit(hat_title, (right_col_x, hat_y))
            hat_y += 30
            
            for i in range(joystick.get_numhats()):
                hat_value = joystick.get_hat(i)
                hat_text = self.small_font.render(f"Hat {i}: {hat_value}", True, WHITE)
                self.screen.blit(hat_text, (right_col_x, hat_y))
                hat_y += 25
        
        # ========== BOTTOM: INSTRUCTIONS ==========
        instructions_y = 460
        instructions = [
            "Press 'Q' to quit  |  Green = pressed  |  Red = Emergency Stop"
        ]
        for instruction in instructions:
            inst_text = self.small_font.render(instruction, True, LIGHT_GRAY)
            self.screen.blit(inst_text, (20, instructions_y))
        
        pygame.display.flip()
    
    async def update_loop(self, joystick):
        """Async task to continuously update the debug screen."""
        if not self.initialized:
            return
        
        clock = pygame.time.Clock()
        
        while True:
            # Process window events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q or event.key == pygame.K_ESCAPE:
                        return
            
            # Draw the debug screen
            if joystick is not None:
                self.draw(joystick)
            
            # Control frame rate (60 FPS)
            clock.tick(60)
            await asyncio.sleep(0.01)  # Small delay to yield control

