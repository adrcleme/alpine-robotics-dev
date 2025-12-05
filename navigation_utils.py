"""
Navigation utilities for waypoint management and navigation computations.
"""

import math
import os
from typing import List, Optional, Tuple

import yaml


def wrap_to_pi(angle: float) -> float:
    """Wrap any angle (radians) to [-pi, pi]."""
    return math.atan2(math.sin(angle), math.cos(angle))


def compute_distance(current_pos: Tuple[float, float], target_pos: Tuple[float, float]) -> float:
    """Compute Euclidean distance between two positions."""
    dx = target_pos[0] - current_pos[0]
    dy = target_pos[1] - current_pos[1]
    return math.hypot(dx, dy)


def compute_heading_error(
    current_pos: Tuple[float, float],
    target_pos: Tuple[float, float],
    current_heading: float
) -> float:
    """Compute heading error from current position to target, in radians, wrapped to [-pi, pi]."""
    # Compute desired heading to target
    dx = target_pos[0] - current_pos[0]
    dy = target_pos[1] - current_pos[1]
    target_heading = math.atan2(dy, dx)
    
    # Compute error
    heading_error = wrap_to_pi(target_heading - current_heading)
    
    return heading_error


def update_waypoint_index(
    current_pos: Tuple[float, float],
    waypoints: List[Tuple[float, float]],
    current_idx: int,
    threshold: float = 2.0
) -> int:
    """Update waypoint index if current waypoint is reached (wraps around if end reached)."""
    if not waypoints or current_idx >= len(waypoints):
        return current_idx
    
    target = waypoints[current_idx]
    distance = compute_distance(current_pos, target)
    
    if distance < threshold:
        # Advance to next waypoint
        new_idx = (current_idx + 1) % len(waypoints)
        return new_idx
    
    return current_idx


def load_waypoints_from_yaml(config_path: str, terrain_name: str) -> Tuple[List[List[float]], Optional[float], Optional[float], Optional[float]]:
    """
    Load waypoints from YAML configuration file.
    
    Args:
        config_path: Path to YAML configuration file
        terrain_name: Name of terrain/waypoint set to load
    
    Returns:
        Tuple of (waypoints, spacing, target_lat, target_lon)
        - waypoints: List of [lat, lon] waypoints
        - spacing: Optional spacing value for interpolation
        - target_lat: Optional target latitude
        - target_lon: Optional target longitude
    
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
        KeyError: If terrain not found
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Waypoint YAML file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream)

    if not data:
        raise ValueError(f"Waypoint YAML {config_path} is empty.")

    terrain_map = data.get("terrains") if isinstance(data.get("terrains"), dict) else data
    entry = terrain_map.get(terrain_name) if isinstance(terrain_map, dict) else None
    if entry is None:
        available = ", ".join(sorted(terrain_map.keys())) if isinstance(terrain_map, dict) else "none"
        raise KeyError(f"Terrain '{terrain_name}' not found in {config_path}. Available: {available}")

    spacing_val = None
    target_latitude = None
    target_longitude = None

    if isinstance(entry, dict):
        spacing_val = entry.get("spacing")
        target_latitude = entry.get("target_lat")
        target_longitude = entry.get("target_lon")
        waypoints = entry.get("waypoints")
        if waypoints is None:
            raise ValueError(f"Terrain '{terrain_name}' entry must include a 'waypoints' list.")
    else:
        waypoints = entry

    # Validate and sanitize waypoints
    sanitized_waypoints = []
    for idx, waypoint in enumerate(waypoints):
        if (
            isinstance(waypoint, (list, tuple))
            and len(waypoint) == 2
            and all(isinstance(coord, (int, float)) for coord in waypoint)
        ):
            sanitized_waypoints.append([float(waypoint[0]), float(waypoint[1])])
        else:
            raise ValueError(
                f"Waypoint #{idx} for terrain '{terrain_name}' must be [lat, lon] floats, got: {waypoint}"
            )

    return sanitized_waypoints, spacing_val, target_latitude, target_longitude

