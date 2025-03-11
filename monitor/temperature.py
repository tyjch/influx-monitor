"""
Temperature classification and state tracking.
"""

from loguru import logger
from typing import Dict, Any, Optional, Tuple
from .constants import TemperatureState, TemperatureConfig, DISCORD_COLORS


class TemperatureTracker:
    """
    Tracks and classifies temperature readings.
    """
    
    def __init__(self, temp_config: TemperatureConfig):
        """
        Initialize the temperature tracker.
        
        Args:
            temp_config: Temperature configuration
        """
        self.temp_config = temp_config
        self.current_state = None
        self.previous_state = None
    
    def classify_temperature(self, temp: float) -> TemperatureState:
        """
        Classify a temperature reading into a temperature state.
        
        Args:
            temp: Temperature in Fahrenheit
            
        Returns:
            The temperature state
        """
        if temp <= self.temp_config.cold_max:
            return TemperatureState.COLD
        elif temp <= self.temp_config.cool_max:
            return TemperatureState.COOL
        elif temp <= self.temp_config.average_max:
            return TemperatureState.AVERAGE
        elif temp <= self.temp_config.warm_max:
            return TemperatureState.WARM
        else:
            return TemperatureState.HOT
    
    def update_state(self, temperature: float) -> bool:
        """
        Update the current temperature state.
        
        Args:
            temperature: The latest temperature reading in Fahrenheit
            
        Returns:
            True if the state changed, False otherwise
        """
        # Apply calibration offset
        calibrated_temp = temperature + self.temp_config.calibration_offset
        
        # Classify temperature
        new_state = self.classify_temperature(calibrated_temp)
        
        # Check for state changes
        if self.current_state != new_state:
            # Save previous state
            self.previous_state = self.current_state
            self.current_state = new_state
            
            # Return true if this isn't the first reading
            return self.previous_state is not None
        
        return False
    
    def get_alert_info(self, temperature: float) -> Dict[str, Any]:
        """
        Get alert information for the current temperature state.
        
        Args:
            temperature: The current temperature in Fahrenheit
            
        Returns:
            Dictionary with alert title, description, and color
        """
        if self.current_state is None:
            return None
        
        # Define alert information based on temperature state
        state_info = {
            TemperatureState.COLD: {
                "title": "Temperature is COLD",
                "description": f"Current temperature: {temperature:.1f}°F (below {self.temp_config.cold_max}°F)",
                "color": DISCORD_COLORS["blue"]
            },
            TemperatureState.COOL: {
                "title": "Temperature is COOL",
                "description": f"Current temperature: {temperature:.1f}°F ({self.temp_config.cold_max}-{self.temp_config.cool_max}°F)",
                "color": DISCORD_COLORS["cyan"]
            },
            TemperatureState.AVERAGE: {
                "title": "Temperature is AVERAGE",
                "description": f"Current temperature: {temperature:.1f}°F ({self.temp_config.cool_max}-{self.temp_config.average_max}°F)",
                "color": DISCORD_COLORS["green"]
            },
            TemperatureState.WARM: {
                "title": "Temperature is WARM",
                "description": f"Current temperature: {temperature:.1f}°F ({self.temp_config.average_max}-{self.temp_config.warm_max}°F)",
                "color": DISCORD_COLORS["yellow"]
            },
            TemperatureState.HOT: {
                "title": "Temperature is HOT",
                "description": f"Current temperature: {temperature:.1f}°F (above {self.temp_config.warm_max}°F)",
                "color": DISCORD_COLORS["red"]
            }
        }
        
        return state_info.get(self.current_state)
    
    def get_current_state(self) -> Optional[TemperatureState]:
        """
        Get the current temperature state.
        
        Returns:
            The current temperature state
        """
        return self.current_state
    
    def get_state_name(self, state: Optional[TemperatureState] = None) -> str:
        """
        Get the name of a temperature state.
        
        Args:
            state: The state to get the name for, or None for current state
            
        Returns:
            The state name as a string
        """
        if state is None:
            state = self.current_state
        
        if state is None:
            return "UNKNOWN"
        
        return state.name