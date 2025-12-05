# GOAT Robot PPO Control System

### Current issue:
Robot turns 4-5 times but heading data doesn't reflect it. Check `data/2025_12_05_175206_goat/` - mocap yaw doesn't change during rotations. Raw mocap data also shows no heading changes.

Check `analyse/compile_csv_data.ipynb` for direct insight.

### To investigate:
When manual checking the w in the qarternion coordinate was the only to change when robot was turning. But the data is converted to normal pitch/raw/roll before sending it (directly on the mocap computer)

Also between the 2 lasts experiments in the `data` file the value of pitch/yax/roll changed but the only diffrence between those 2 eperiments were the posiitons in x,y of the robot. this hsould not have an impact.




## Quick Use

```
.
├── goat_mocap_ppo.py      # Main control script (RUN THIS ONE)
├── mocap_client.py        # Motion capture client
├── ppo_controller.py      # PPO neural network controller
├── navigation_utils.py    # Waypoint and navigation utilities
├── waypoints.yaml         # Waypoint configuration
├── latest.zip             # PPO model file
├── analyse/               # Data analysis notebooks
├── data/                  # Data from mocap experiments
├── tests/                 # No need to touch this
└── archive/               # Archived code
```

## Mocap Setup 

- [ ] source config/setup_ROS.sh --pkg --srv 9
- [ ] ros2 topic echo /mocap_node/EIGER/pose
- [ ] ros2 run jetbot_data_recorder mocap_state_recorder

## Data Output

All data is saved to timestamped folders (`YYYY_MM_DD_HHMMSS_goat/`):

- **Main data logs**: CSV files with sensor data, control commands, and navigation state
- **Mocap raw data**: `mocap_raw_*.csv` with all raw mocap measurements (position, orientation, velocity)
