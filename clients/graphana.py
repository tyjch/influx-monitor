import time
import requests
from loguru import logger
from typing import Dict, Any, Optional


class GrafanaClient:

    def __init__(self, grafana_url: str, api_key: str, dashboard_uid: str, refresh_interval: int = 300):
        """
        Initialize the Grafana client.
        
        Args:
            grafana_url: Base URL of the Grafana instance
            api_key: Grafana API key with read permissions
            dashboard_uid: UID of the dashboard containing variables
            refresh_interval: How often to refresh variables (seconds)
        """
        self.grafana_url = grafana_url.rstrip('/')
        self.api_key = api_key
        self.dashboard_uid = dashboard_uid
        self.refresh_interval = refresh_interval
        self.last_refresh_time = 0
        self.variables_cache = {}
        
    def get_variables(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get variables from Grafana dashboard.
        
        Args:
            force_refresh: Whether to force a refresh regardless of cache
            
        Returns:
            Dictionary of variable values
        """
        current_time = int(time.time())
        
        # Check if we need to refresh
        if force_refresh or current_time - self.last_refresh_time > self.refresh_interval:
            try:
                self._refresh_variables()
                self.last_refresh_time = current_time
            except Exception as e:
                logger.error(f"Error refreshing Grafana variables: {e}")
                # If we failed to refresh but have a cached config, use that
                if not self.variables_cache:
                    raise
        
        return self.variables_cache

    def _refresh_variables(self) -> None:
        """
        Refresh variables from Grafana dashboard.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Get dashboard information first
        url = f"{self.grafana_url}/api/dashboards/uid/{self.dashboard_uid}"
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        dashboard_info = response.json()
        
        # Extract variable information from the dashboard
        dashboard_data = dashboard_info.get("dashboard", {})
        templates = dashboard_data.get("templating", {}).get("list", [])
        
        variables = {}
        
        # Process each variable
        for template in templates:
            name = template.get("name")
            current = template.get("current", {})
            value = current.get("value")
            
            if name and value is not None:
                # Try to convert value to appropriate type
                try:
                    # Check if it's a number with decimal point
                    if isinstance(value, str) and "." in value:
                        variables[name] = float(value)
                    # Check if it's an integer
                    elif isinstance(value, str) and value.isdigit():
                        variables[name] = int(value)
                    else:
                        variables[name] = value
                except ValueError:
                    variables[name] = value
                
                # Process prefixed variables into categories
                # e.g., temp_cold_max -> "temperature": {"cold_max": value}
                if "_" in name:
                    prefix, key = name.split("_", 1)
                    if prefix not in variables:
                        variables[prefix] = {}
                    variables[prefix][key] = variables[name]
        
        self.variables_cache = variables
        logger.info(f"Refreshed variables from Grafana: {len(variables)} values")
    
    def get_temperature_variables(self) -> Dict[str, Any]:
        """
        Get temperature-specific variables.
        
        Returns:
            Dictionary of temperature configuration values
        """
        variables = self.get_variables()
        return variables.get("temp", {})
    
    def update_temperature_config(self, temp_config):
        """
        Update a TemperatureConfig object with values from Grafana.
        
        Args:
            temp_config: TemperatureConfig object to update
            
        Returns:
            True if any values were updated, False otherwise
        """
        temp_vars = self.get_temperature_variables()
        if not temp_vars:
            return False
            
        updated = False
        
        # Map variable names to config attributes
        mappings = {
            'cold_max': 'cold_max',
            'cool_max': 'cool_max',
            'average_max': 'average_max',
            'warm_max': 'warm_max',
            'calibration_offset': 'calibration_offset',
            'min_realistic_temp': 'min_realistic_temp',
            'misposition_time_threshold': 'misposition_time_threshold',
            'stabilization_threshold': 'stabilization_threshold',
            'min_stabilization_time': 'min_stabilization_time',
            'room_temp_threshold': 'room_temp_threshold'
        }
        
        # Update config with values from Grafana
        for var_name, attr_name in mappings.items():
            if var_name in temp_vars and hasattr(temp_config, attr_name):
                try:
                    current_value = getattr(temp_config, attr_name)
                    new_value = temp_vars[var_name]
                    
                    # Convert types if needed
                    if isinstance(current_value, int) and not isinstance(new_value, int):
                        new_value = int(float(new_value))
                    elif isinstance(current_value, float) and not isinstance(new_value, float):
                        new_value = float(new_value)
                    
                    if current_value != new_value:
                        setattr(temp_config, attr_name, new_value)
                        logger.info(f"Updated {attr_name} from {current_value} to {new_value}")
                        updated = True
                        
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error updating {attr_name}: {e}")
        
        return updated