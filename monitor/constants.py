"""
Constants and enums for the influx monitor.
"""

from enum import Enum, auto
from dataclasses import dataclass


class SensorState(Enum):
    """Enum representing the possible states of the temperature sensor."""
    UNKNOWN = auto()
    DISCONNECTED = auto()
    CONNECTED = auto()
    MISPOSITIONED = auto()


class TemperatureState(Enum):
    """Enum representing the temperature ranges."""
    COLD = auto()
    COOL = auto()
    AVERAGE = auto()
    WARM = auto()
    HOT = auto()


@dataclass
class TemperatureConfig:
    """Configuration for temperature thresholds and calibration."""
    cold_max: float = 96.5
    cool_max: float = 97.0
    average_max: float = 98.0
    warm_max: float = 99.0
    # hot has no max

    # Calibration offset to add to raw sensor readings
    calibration_offset: float = 0.0
    
    # Minimum realistic body temperature (°F)
    min_realistic_temp: float = 94.0
    
    # Maximum time (minutes) to reach realistic body temp before considering mispositioned
    misposition_time_threshold: int = 5

    # Rate of change threshold to exit stabilization mode (°F per minute)
    stabilization_threshold: float = 0.1
    
    # Duration (seconds) to wait in stabilization mode before checking rate of change
    min_stabilization_time: int = 60

    # Maximum room temperature difference for determining disconnection (°F)
    room_temp_threshold: float = 10.0


# Default configuration for general settings
DEFAULT_CHECK_INTERVAL = 60  # seconds
DEFAULT_OFFLINE_THRESHOLD = 300  # seconds

# Discord embed colors for different states
DISCORD_COLORS = {
    "green": 0x00FF00,      # Success/online
    "red": 0xFF0000,        # Error/offline/hot
    "blue": 0x0000FF,       # Cold
    "cyan": 0x00FFFF,       # Cool
    "yellow": 0xFFFF00,     # Warm
    "orange": 0xFFA500      # Warning/mispositioned
}

# Grafana configuration
DEFAULT_GRAFANA_REFRESH_INTERVAL = 300  # seconds