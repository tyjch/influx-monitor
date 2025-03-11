"""
Sensor state tracking and detection functionality.
"""

from loguru import logger
from datetime import datetime
from typing import List, Dict, Any, Optional
from .constants import SensorState, TemperatureConfig


class SensorStateTracker:
    """
    Tracks and determines the state of temperature sensors.
    """
    
    def __init__(self, temp_config: TemperatureConfig):
        """
        Initialize the sensor state tracker.
        
        Args:
            temp_config: Temperature configuration
        """
        self.temp_config = temp_config
        self.state = SensorState.UNKNOWN
        self.stabilization_mode = False
        self.stabilization_start_time = None
        self.recent_temperatures = []
        self.recent_room_temps = []
    
    def determine_state(self, 
                         ds18b20_temps: List[Dict[str, Any]], 
                         si7021_temps: List[Dict[str, Any]]) -> SensorState:
        """
        Determine the current state of the DS18B20 sensor.
        
        Args:
            ds18b20_temps: Recent DS18B20 temperature readings
            si7021_temps: Recent SI7021 temperature readings (room temp)
            
        Returns:
            The current sensor state
        """
        if not ds18b20_temps:
            return SensorState.DISCONNECTED
        
        # Store recent temperatures for rate-of-change calculations
        self.recent_temperatures = [reading['value'] for reading in ds18b20_temps]
        
        # Get the latest room temperature
        room_temp = None
        if si7021_temps:
            room_temp = si7021_temps[-1]['value']
            self.recent_room_temps = [reading['value'] for reading in si7021_temps]
        
        # Apply calibration offset to the latest temperature
        latest_temp = ds18b20_temps[-1]['value'] + self.temp_config.calibration_offset
        
        # If we have a previous state and recent readings
        if self.state != SensorState.UNKNOWN and len(ds18b20_temps) >= 2:
            # Calculate temperature change rate (°F per minute)
            time_diff = (ds18b20_temps[-1]['time'] - ds18b20_temps[0]['time']).total_seconds() / 60
            if time_diff > 0:
                temp_diff = ds18b20_temps[-1]['value'] - ds18b20_temps[0]['value']
                rate_of_change = temp_diff / time_diff
            else:
                rate_of_change = 0
            
            # Handle stabilization mode
            if self.stabilization_mode:
                # Check if we've been in stabilization mode long enough
                time_in_stabilization = (datetime.now() - self.stabilization_start_time).total_seconds()
                
                if time_in_stabilization >= self.temp_config.min_stabilization_time:
                    # If temperature change has slowed down, exit stabilization mode
                    if abs(rate_of_change) < self.temp_config.stabilization_threshold:
                        logger.info("Exiting stabilization mode: rate of change %.3f°F/min is below threshold %.3f°F/min",
                                   rate_of_change, self.temp_config.stabilization_threshold)
                        self.stabilization_mode = False
                        
                        # Check if the sensor has reached a realistic body temperature
                        if latest_temp >= self.temp_config.min_realistic_temp:
                            # Sensor is properly connected
                            return SensorState.CONNECTED
                        else:
                            # If we haven't reached a realistic temperature after stabilization,
                            # the sensor might be mispositioned
                            if (datetime.now() - self.stabilization_start_time).total_seconds() > (self.temp_config.misposition_time_threshold * 60):
                                return SensorState.MISPOSITIONED
            
            # Detect if sensor has been disconnected (significant drop towards room temperature)
            if self.state == SensorState.CONNECTED:
                # If temperature is dropping rapidly or is close to room temperature
                if rate_of_change < -1.0:  # Dropping more than 1°F per minute
                    return SensorState.DISCONNECTED
                elif room_temp and abs(latest_temp - room_temp) < self.temp_config.room_temp_threshold:
                    return SensorState.DISCONNECTED
            
            # Detect if sensor has been connected (rising from room temperature)
            if self.state == SensorState.DISCONNECTED:
                if rate_of_change > 0.5:  # Rising more than 0.5°F per minute
                    self.stabilization_mode = True
                    self.stabilization_start_time = datetime.now()
                    return SensorState.CONNECTED
        
        # Initial state determination
        if latest_temp >= self.temp_config.min_realistic_temp:
            # If temperature is already in a realistic range, consider it connected
            return SensorState.CONNECTED
        elif room_temp and abs(latest_temp - room_temp) < self.temp_config.room_temp_threshold:
            # If temperature is close to room temperature, consider it disconnected
            return SensorState.DISCONNECTED
        else:
            # Otherwise unknown
            return SensorState.UNKNOWN
    
    def update_state(self, new_state: SensorState) -> bool:
        """
        Update the current sensor state.
        
        Args:
            new_state: The new sensor state
            
        Returns:
            True if the state changed, False otherwise
        """
        if new_state != self.state:
            logger.info("Sensor state changed: %s -> %s", 
                       self.state.name if self.state != SensorState.UNKNOWN else "UNKNOWN", 
                       new_state.name)
            
            old_state = self.state
            self.state = new_state
            return True
        
        return False
    
    def is_in_stabilization_mode(self) -> bool:
        """
        Check if the sensor is in stabilization mode.
        
        Returns:
            True if in stabilization mode, False otherwise
        """
        return self.stabilization_mode
    
    def enter_stabilization_mode(self) -> None:
        """Enter stabilization mode."""
        self.stabilization_mode = True
        self.stabilization_start_time = datetime.now()
        logger.info("Entering stabilization mode")