import pygame
import sys
import os
import json
import math
import time

# Initialize pygame and set environment variable for background events
os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"
os.environ["SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS"] = "0"  # Prevent minimizing when focus is lost
pygame.init()
pygame.joystick.init()

# Set up the display
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("M-/D-Speed Visualizer")

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
BACKGROUND = (240, 240, 240)

# Config file for axis mappings
CONFIG_FILE = "gamepad_config.json"

# Default configuration
default_config = {
    "left_x_axis": 0,
    "left_y_axis": 1,
    "deadzone": 0.05
}

# Load or create configuration
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            print(f"Error reading config file. Using defaults.")
            return default_config
    else:
        # Create default config file
        with open(CONFIG_FILE, "w") as f:
            json.dump(default_config, f, indent=4)
        return default_config

# Save configuration
def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

# Load config
config = load_config()

# Check for connected gamepads
joystick_count = pygame.joystick.get_count()
if joystick_count == 0:
    print("No gamepads found! Please connect a gamepad and try again.")
    pygame.quit()
    sys.exit()

# Initialize the first gamepad
joystick = pygame.joystick.Joystick(0)
joystick.init()
print(f"Gamepad detected: {joystick.get_name()}")
print(f"Number of axes: {joystick.get_numaxes()}")

# Apply deadzone to stick values
def apply_deadzone(value, deadzone):
    if abs(value) < deadzone:
        return 0
    return value

# Function to convert cartesian to polar coordinates
def cart_to_polar(x, y):
    r = math.sqrt(x*x + y*y)
    theta = math.atan2(y, x)
    return r, theta

# Function to convert polar to cartesian coordinates
def polar_to_cart(r, theta):
    x = r * math.cos(theta)
    y = r * math.sin(theta)
    return x, y

# Target zone class for curved rectangles that follow the joystick boundary
class CurvedRectangleTargetZone:
    def __init__(self, start_angle, end_angle, inner_radius, outer_radius, color=GREEN):
        self.start_angle = start_angle  # in radians
        self.end_angle = end_angle      # in radians
        self.inner_radius = inner_radius  # distance from center (0-1)
        self.outer_radius = outer_radius  # distance from center (0-1)
        self.color = color
        self.active = True
    
    def is_stick_in_zone(self, stick_x, stick_y):
        # Convert stick position to polar coordinates
        r, theta = cart_to_polar(stick_x, stick_y)
        
        # Normalize angle to 0-2π if needed
        if theta < 0:
            theta += 2 * math.pi
            
        # Check if angle is within bounds
        angle_in_range = False
        if self.start_angle <= self.end_angle:
            angle_in_range = self.start_angle <= theta <= self.end_angle
        else:  # Handles the case where the zone crosses the 0 angle
            angle_in_range = theta >= self.start_angle or theta <= self.end_angle
            
        # Check if radius is within bounds
        radius_in_range = self.inner_radius <= r <= self.outer_radius
        
        # Return true if both angle and radius are in range
        return angle_in_range and radius_in_range

    def draw(self, surface, center_x, center_y, scale):
        # Base color with transparency
        base_color = (*self.color, 180)
        
        # Create a surface for the transparent target zone
        target_surf = pygame.Surface((scale * 2 + 10, scale * 2 + 10), pygame.SRCALPHA)
        
        # Draw the curved rectangle on the surface
        points = []
        
        # Number of segments to approximate the curve (higher = smoother)
        segments = 20
        
        # Generate points for the filled polygon representing the curved rectangle
        angle_range = self.end_angle - self.start_angle
        if angle_range < 0:
            angle_range += 2 * math.pi
        
        # Add points for outer arc (going clockwise)
        for i in range(segments + 1):
            angle = self.start_angle + (angle_range * i / segments)
            x, y = polar_to_cart(self.outer_radius * scale, angle)
            points.append((x + scale + 5, y + scale + 5))
        
        # Add points for inner arc (going counter-clockwise)
        for i in range(segments, -1, -1):
            angle = self.start_angle + (angle_range * i / segments)
            x, y = polar_to_cart(self.inner_radius * scale, angle)
            points.append((x + scale + 5, y + scale + 5))
        
        # Draw filled polygon
        pygame.draw.polygon(target_surf, base_color, points)
        
        # Draw outline
        pygame.draw.polygon(target_surf, BLACK, points, 2)
        
        # Blit the surface onto the main surface, centered properly
        surface.blit(target_surf, (center_x - scale - 5, center_y - scale - 5))

def draw_stick(x, y, x_pos, y_pos, color, label, targets=None):
    """Draw an analog stick visualization"""
    # Scale for visualization (95% of the circle radius)
    scale = 95
    
    # Draw the outer boundary circle
    pygame.draw.circle(screen, BLACK, (x, y), 100, 2)
    
    # Draw coordinate lines
    pygame.draw.line(screen, BLACK, (x - 100, y), (x + 100, y), 1)
    pygame.draw.line(screen, BLACK, (x, y - 100), (x, y + 100), 1)
    
    # Draw target zones if provided
    if targets:
        for target in targets:
            if target.active or show_all_targets:  # Modified to check show_all_targets
                target.draw(screen, x, y, scale)
    
    # Calculate stick position
    stick_x = x + x_pos * scale
    stick_y = y + y_pos * scale
    
    # Draw line from center to stick position
    pygame.draw.line(screen, color, (x, y), (stick_x, stick_y), 3)
    
    # Draw the stick position with smaller radius
    pygame.draw.circle(screen, color, (stick_x, stick_y), 8)  # Changed from 15 to 8
    
    # Draw the label
    font = pygame.font.Font(None, 36)
    text = font.render(label, True, BLACK)
    text_rect = text.get_rect(center=(x, y + 130))
    screen.blit(text, text_rect)
    
    # Show the values
    values_text = font.render(f"X: {x_pos:.2f}, Y: {y_pos:.2f}", True, BLACK)
    values_rect = values_text.get_rect(center=(x, y + 170))
    screen.blit(values_text, values_rect)

def debug_draw_all_axes(joystick):
    """Draw debug information for all axes"""
    font = pygame.font.Font(None, 24)
    num_axes = joystick.get_numaxes()
    
    pygame.draw.rect(screen, (220, 220, 220), (10, 60, 400, 30 + num_axes * 25))
    
    title = font.render("DEBUG: All Axis Values", True, BLACK)
    screen.blit(title, (20, 70))
    
    for i in range(num_axes):
        value = joystick.get_axis(i)
        text = font.render(f"Axis {i}: {value:.3f}", True, BLACK)
        screen.blit(text, (20, 100 + i * 25))

    # Highlight configured axes
    text = font.render(f"Left stick: X=Axis {config['left_x_axis']}, Y=Axis {config['left_y_axis']}", 
                     True, RED)
    screen.blit(text, (180, 100))

# Create some sample curved rectangle target zones
target_zones = [
    # Top-left quadrant (moved to first position)
    CurvedRectangleTargetZone(5*math.pi/4, 7*math.pi/4, 0.45, 0.7, GREEN),
    
    # Top-right quadrant
    CurvedRectangleTargetZone(-math.pi/4, math.pi/4, 0.29, 0.50, GREEN),
    
    # Bottom-left quadrant
    CurvedRectangleTargetZone(3*math.pi/4, 5*math.pi/4, 0.29, 0.50, GREEN)
]

# Only show one target at a time initially
current_target = 0
# Deactivate all targets initially except the first one
for i, target in enumerate(target_zones):
    target.active = (i == current_target)

# Flag to show all targets at once
show_all_targets = False

# Add flag to track if we're in configuration mode
config_mode = False
target_mode = True  # Start with target mode active
currently_configuring = None
config_instructions = [
    "Press 1-2 keys to assign an axis number",
    "Left stick X (1), Left stick Y (2)",
    "Press D to toggle deadzone configuration",
    "Press S to save and exit config mode"
]

# Main game loop
clock = pygame.time.Clock()
running = True
show_debug = False  # Debug mode off by default
message = ""
message_timer = 0

# For measuring time delta between frames
last_time = time.time()

while running:
    # Calculate delta time for smooth animations
    current_time = time.time()
    dt = current_time - last_time
    last_time = current_time
    
    # Ensure events are processed even when not in focus
    pygame.event.pump()
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_c:
                # Toggle configuration mode
                config_mode = not config_mode
                if config_mode:
                    print("Entering config mode")
                else:
                    print("Exiting config mode")
            elif event.key == pygame.K_d:
                # Toggle debug view
                show_debug = not show_debug
            elif event.key == pygame.K_t:
                # Toggle target mode
                target_mode = not target_mode
                message = "Target Mode: " + ("ON" if target_mode else "OFF")
                message_timer = 2.0  # Show message for 2 seconds
            elif event.key == pygame.K_a:
                # Toggle showing all targets at once
                show_all_targets = not show_all_targets
                message = "Show All Targets: " + ("ON" if show_all_targets else "OFF")
                message_timer = 2.0
            elif event.key == pygame.K_n:
                # Go to next target
                if target_mode and not show_all_targets:
                    # Mark current target as inactive
                    target_zones[current_target].active = False
                    # Move to next target
                    current_target = (current_target + 1) % len(target_zones)
                    # Activate new target
                    target_zones[current_target].active = True
                    message = f"Target {current_target + 1}/{len(target_zones)}"
                    message_timer = 1.0
            elif event.key == pygame.K_p:
                # Go to previous target
                if target_mode and not show_all_targets:
                    # Mark current target as inactive
                    target_zones[current_target].active = False
                    # Move to previous target
                    current_target = (current_target - 1) % len(target_zones)
                    # Activate new target
                    target_zones[current_target].active = True
                    message = f"Target {current_target + 1}/{len(target_zones)}"
                    message_timer = 1.0
            elif event.key == pygame.K_r:
                # Reset all targets
                show_all_targets = False
                for i, target in enumerate(target_zones):
                    target.active = (i == current_target)
            
            # Configuration key handling
            if config_mode:
                if event.key == pygame.K_1:
                    currently_configuring = "left_x_axis"
                    print("Move the LEFT STICK LEFT and RIGHT, then press a number key 0-9")
                elif event.key == pygame.K_2:
                    currently_configuring = "left_y_axis"
                    print("Move the LEFT STICK UP and DOWN, then press a number key 0-9")
                elif event.key >= pygame.K_0 and event.key <= pygame.K_9:
                    if currently_configuring:
                        axis_num = event.key - pygame.K_0
                        if axis_num < joystick.get_numaxes():
                            config[currently_configuring] = axis_num
                            print(f"Set {currently_configuring} to axis {axis_num}")
                            currently_configuring = None
                        else:
                            print(f"Axis {axis_num} doesn't exist on this controller")
                elif event.key == pygame.K_s:
                    save_config(config)
                    config_mode = False
                    print("Configuration saved")
                elif event.key == pygame.K_d:
                    # Increase/decrease deadzone
                    currently_configuring = "deadzone"
                    print(f"Current deadzone: {config['deadzone']}")
                    print("Use + and - keys to adjust")
                
            if currently_configuring == "deadzone":
                if event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                    config['deadzone'] = min(0.5, config['deadzone'] + 0.01)
                    print(f"Deadzone: {config['deadzone']:.2f}")
                elif event.key == pygame.K_MINUS:
                    config['deadzone'] = max(0.0, config['deadzone'] - 0.01)
                    print(f"Deadzone: {config['deadzone']:.2f}")
    
    # Clear the screen
    screen.fill(BACKGROUND)
    
    # Get stick values using config mappings
    try:
        left_x = apply_deadzone(joystick.get_axis(config["left_x_axis"]), config["deadzone"])
        left_y = apply_deadzone(joystick.get_axis(config["left_y_axis"]), config["deadzone"])
    except:
        # Fallback if axis doesn't exist
        print("Error reading axis. Check your configuration.")
        left_x, left_y = 0, 0
    
    # Draw the stick visualization with targets if target mode is on
    visible_targets = target_zones if target_mode else None
    draw_stick(WIDTH // 2, HEIGHT // 2, left_x, left_y, RED, "Analog Stick", visible_targets)
    
    # Show debug info if enabled
    if show_debug:
        debug_draw_all_axes(joystick)
    
    # Add instructions
    font = pygame.font.Font(None, 24)
    if config_mode:
        for i, line in enumerate(config_instructions):
            text = font.render(line, True, GREEN)
            screen.blit(text, (20, 20 + i * 25))
    else:
        instructions = font.render("Move stick | T: Toggle Targets | A: Show All | N/P: Next/Prev | ESC: Quit", True, BLACK)
        screen.blit(instructions, (20, 20))
    
    # Show display mode status
    if target_mode:
        mode_text = "Mode: " + ("All Targets" if show_all_targets else f"Target {current_target + 1}/{len(target_zones)}")
        mode_font = pygame.font.Font(None, 28)
        mode_label = mode_font.render(mode_text, True, BLACK)
        screen.blit(mode_label, (WIDTH//2 - 80, 50))
    
    # Show message if there is one
    if message and message_timer > 0:
        msg_font = pygame.font.Font(None, 36)
        msg_text = msg_font.render(message, True, GREEN)
        msg_rect = msg_text.get_rect(center=(WIDTH // 2, 90))
        screen.blit(msg_text, msg_rect)
        message_timer -= dt
    
    # Add gamepad information
    info_text = font.render(f"Connected: {joystick.get_name()}", True, BLACK)
    screen.blit(info_text, (20, HEIGHT - 30))
    
    # Add deadzone info
    dz_text = font.render(f"Deadzone: {config['deadzone']:.2f}", True, BLACK)
    screen.blit(dz_text, (WIDTH - 150, HEIGHT - 30))
    
    # Update the display
    pygame.display.flip()
    
    # Force rendering to continue regardless of focus
    pygame.time.delay(5)  # Small delay to prevent hogging CPU
    clock.tick(60)  # 60 FPS

pygame.quit()
sys.exit()
