# GOAT Robot PPO Control System

Autonomous navigation system for the GOAT robot using PPO (Proximal Policy Optimization) reinforcement learning. The system uses motion capture for localization and follows waypoint-based navigation paths.

## Overview

This system enables autonomous waypoint navigation using:
- **PPO Neural Network Controller**: Trained policy for generating wheel velocity commands
- **Motion Capture Integration**: Real-time position and orientation tracking via UDP
- **Waypoint Navigation**: YAML-configured waypoint following with automatic progression
- **Data Logging**: Comprehensive CSV logging of sensor data, control commands, and navigation state

## Quick Start

### Main Entry Point
```bash
python goat_mocap_ppo.py
```

### Command Line Options
- `--verbose`: Print debug information
- `--debug-screen`: Show visual debug screen for controller inputs

### Terminal Control Menu
Once running, use the interactive menu:
- `1` or `ppo` - Toggle PPO control ON/OFF
- `2` or `f1` - Set failure mode 1
- `3` or `f2` - Set failure mode 2
- `4` or `stop` - Emergency stop
- `5` or `status` - Show current status
- `q` or `quit` - Exit program

## Project Structure

```
├── goat_mocap_ppo.py      # Main control script (entry point)
├── mocap_client.py        # Motion capture UDP client
├── ppo_controller.py      # PPO neural network controller
├── navigation_utils.py    # Waypoint and navigation utilities
├── waypoints.yaml         # Waypoint configuration
├── latest.zip             # PPO model file (trained policy)
├── analyse/               # Data analysis notebooks
├── data/                  # Experimental data logs
└── goat_gps_tracking_*/   # ESP32 Arduino firmware
```

## Configuration

### Motion Capture Setup
1. Ensure mocap system is running and publishing to UDP port 9091
2. Configure IP address in `goat_mocap_ppo.py` (default: `192.168.1.5`)
3. Mocap data format: position (x, y, z) and quaternion orientation

### Waypoints
Edit `waypoints.yaml` to define navigation paths:
```yaml
terrains:
  default:
    waypoints:
      - [x1, y1]
      - [x2, y2]
```

### Robot Configuration
- **ESP32 IP**: `192.168.1.10` (configured in `goat_mocap_ppo.py`)
- **Track Width**: 0.35m (distance between wheels)
- **Waypoint Threshold**: 0.75m (distance to consider waypoint reached)

## Data Output

All data is saved to timestamped folders (`YYYY_MM_DD_HHMMSS_goat/`):
- **Main logs**: CSV files with sensor data, control commands, and navigation state
- **Mocap raw data**: `mocap_raw_*.csv` with all raw mocap measurements

## Dependencies

- `stable-baselines3` - PPO model loading and inference
- `numpy` - Numerical computations
- `pandas` - Data logging
- `pygame` - Optional joystick support (for data logging)
- `pyyaml` - Waypoint configuration parsing

## Architecture

1. **Mocap Client** (`mocap_client.py`): Receives position/orientation data via UDP, converts quaternions to heading
2. **PPO Controller** (`ppo_controller.py`): Maintains 12-step history buffers, generates wheel velocity commands from neural network
3. **Navigation Utils** (`navigation_utils.py`): Computes heading errors, distances, and waypoint management
4. **Main Loop** (`goat_mocap_ppo.py`): Orchestrates sensor reading, control computation, command sending, and data logging

## Notes

- The system uses absolute mocap coordinates for navigation
- PPO controller requires a 12-step history buffer for each input (position, heading error, distance)
- Commands are sent at ~20Hz (PREDICTION_DT = 0.045s)
- Data is automatically saved every 5 seconds during operation
