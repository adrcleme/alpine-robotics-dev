"""
NN Controller for PPO-based robot control.

Handles model loading, input buffering, and command computation for neural network control.
"""

import math
import os
from typing import List, Optional, Tuple

import numpy as np
from stable_baselines3 import PPO

# Track width for converting angular velocity to wheel velocities
TRACK_WIDTH = 0.35


def wrap_to_pi(angle: float) -> float:
    """Wrap any angle (radians) to [-pi, pi]."""
    return math.atan2(math.sin(angle), math.cos(angle))


class PPOController:
    """
    Neural network controller for robot navigation using PPO policy.
    
    Maintains buffers of navigation inputs (position, heading error, distance)
    and generates wheel velocity commands from the neural network.
    """
    
    HISTORY = 12  # Number of previous values to buffer for each input type

    def __init__(self, model_path: str, track_width: float = TRACK_WIDTH):
        """
        Initialize the PPO controller.
        
        Args:
            model_path: Path to the PPO model file (.zip)
            track_width: Distance between wheels in meters (default: 0.35)
        """
        self.model_path = model_path
        self.model: Optional[PPO] = None
        self.track_width = track_width
        
        # Input buffers (12-step history)
        self.position_buffer: List[Tuple[float, float]] = []
        self.heading_error_buffer: List[float] = []
        self.distance_buffer: List[float] = []
        self.target_position: Tuple[float, float] = (0.0, 0.0)

        # Scaling factors for normalization
        self.position_scale = 5.0
        self.distance_scale = 10.0
        self.heading_scale = math.pi
        
        # Velocity limits
        self.v_max = 0.5
        self.omega_max = 2.7 #3.0

        self._load_model()

    def _load_model(self):
        """Load the PPO model from file."""
        if not os.path.exists(self.model_path):
            print(f"[PPOController] Model not found: {self.model_path}")
            return
        try:
            self.model = PPO.load(self.model_path)
            print(f"[PPOController] Loaded policy from {self.model_path}")
        except Exception as exc:
            print(f"[PPOController] Failed to load policy: {exc}")
            self.model = None

    @staticmethod
    def _pad_history(history, length, pad_value):
        """
        Pad history to specified length.
        
        If history is shorter than length, pad with the last value.
        If history is empty, pad with pad_value.
        """
        if not history:
            return [pad_value for _ in range(length)]
        padded = history[-length:]
        pad_needed = length - len(padded)
        if pad_needed > 0:
            padded = padded + [padded[-1]] * pad_needed
        return padded

    def update_buffers(
        self,
        position_xy: Tuple[float, float],
        heading_error: float,
        distance: float,
        target_xy: Tuple[float, float],
    ):
        """
        Update input buffers with new navigation data.
        
        Args:
            position_xy: Current robot position (x, y) in meters
            heading_error: Heading error in radians
            distance: Distance to target in meters
            target_xy: Target position (x, y) in meters
        """
        # Skip if any value is NaN
        if any(math.isnan(val) for val in (*position_xy, heading_error, distance, *target_xy)):
            return
        
        self.position_buffer.append((float(position_xy[0]), float(position_xy[1])))
        self.heading_error_buffer.append(wrap_to_pi(float(heading_error)))
        self.distance_buffer.append(float(distance))
        self.target_position = (float(target_xy[0]), float(target_xy[1]))

    def compute_command(self) -> Optional[Tuple[float, float, float, float]]:
        """
        Compute wheel velocity commands from buffered observations.
        
        Returns:
            Tuple of (v_left, v_right, v_linear, v_angular) or None if model unavailable
            - v_left, v_right: Wheel velocities in m/s (normalized -1 to 1)
            - v_linear: Linear velocity in m/s
            - v_angular: Angular velocity in rad/s
        """
        if self.model is None:
            return None

        # Pad buffers to HISTORY length
        positions = self._pad_history(self.position_buffer, self.HISTORY, (0.0, 0.0))
        headings = self._pad_history(self.heading_error_buffer, self.HISTORY, 0.0)
        distances = self._pad_history(self.distance_buffer, self.HISTORY, 0.0)

        # Construct observation vector:
        # - 12 positions (x, y) = 24 values
        # - 12 heading errors = 12 values
        # - 12 distances = 12 values
        # - 1 target position (x, y) = 2 values
        # Total: 50 values
        obs = []
        
        for x, y in positions:
            obs.extend([x / self.position_scale, y / self.position_scale])      # Add position history (normalized)
        obs.extend([wrap_to_pi(h) / self.heading_scale for h in headings])      # Add heading error history (normalized)
        obs.extend([d / self.distance_scale for d in distances])                # Add distance history (normalized)
        obs.extend([                                                            # Add target position (normalized)
            self.target_position[0] / self.position_scale,
            self.target_position[1] / self.position_scale,
        ])

        # Convert to numpy array and predict
        obs_arr = np.asarray(obs, dtype=np.float32)
        try:
            action, _ = self.model.predict(obs_arr, deterministic=True)
        except Exception as exc:
            print(f"[PPOController] Prediction failed: {exc}")
            return None

        action = np.asarray(action).flatten()
        if action.size < 2:
            return None

        # Normalize action to [-1, 1]
        linear_norm = float(np.clip(action[0], -1.0, 1.0))
        angular_norm = float(np.clip(action[1], -1.0, 1.0))

        # Scale to actual velocities
        v_linear = linear_norm * self.v_max
        v_angular = angular_norm * self.omega_max

        # Convert to wheel velocities
        v_left = v_linear - (v_angular * self.track_width / 2.0)
        v_right = v_linear + (v_angular * self.track_width / 2.0)

        return v_left, v_right, v_linear, v_angular

