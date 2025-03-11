"""
Main InfluxMonitor class that coordinates monitoring and alerting.
"""

import os
import time
import asyncio
import yaml
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from loguru import logger

from .constants import SensorState, TemperatureState, TemperatureConfig, DISCORD_COLORS, DEFAULT_CHECK_INTERVAL, DEFAULT_OFFLINE_THRESHOLD
from .sensor_state import SensorStateTracker
from .temperature import TemperatureTracker
from clients.influx_client import InfluxClient
from clients.discord_client import DiscordClient
from clients.grafana_client import GrafanaClient


class InfluxMonitor:
    """
    Main class that monitors InfluxDB data and sends alerts.
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize the influx monitor.
        
        Args:
            config_path: Path to the configuration file
        """
        # Load environment variables
        load_dotenv()
        
        # Load configuration
        self.load_config(config_path)
        
        # Initialize clients
        self.init_clients()
        
        # Initialize state trackers
        self.sensor_tracker = SensorStateTracker(self.temp_config)
        self.temp_tracker = TemperatureTracker(self.temp_config)
        
        # Initialize state variables
        self.pi_online = False
        self.last_online_check = datetime.now() - timedelta(minutes=10)  # Force initial check
        self.last_grafana_refresh = 0
    
    def load_config(self, config_path: str) -> None:
        """Load configuration from YAML file and environment variables."""
        try:
            # Start with environment-based configuration
            self.temp_config = TemperatureConfig(
                cold_max=float(os.getenv('TEMP_COLD_MAX', 96.5)),
                cool_max=float(os.getenv('TEMP_COOL_MAX', 97.0)),
                average_max=float(os.getenv('TEMP_AVERAGE_MAX', 98.0)),
                warm_max=float(os.getenv('TEMP_WARM_MAX', 99.0)),
                calibration_offset=float(os.getenv('TEMP_CALIBRATION_OFFSET', 0.0)),
                min_realistic_temp=float(os.getenv('TEMP_MIN_REALISTIC', 94.0)),
                misposition_time_threshold=int(os.getenv('TEMP_MISPOSITION_THRESHOLD', 5)),
                stabilization_threshold=float(os.getenv('TEMP_STABILIZATION_THRESHOLD', 0.1)),
                min_stabilization_time=int(os.getenv('TEMP_MIN_STABILIZATION_TIME', 60)),
                room_temp_threshold=float(os.getenv('TEMP_ROOM_THRESHOLD', 10.0))
            )
            
            # General settings
            self.check_interval = int(os.getenv('CHECK_INTERVAL', DEFAULT_CHECK_INTERVAL))
            self.offline_threshold = int(os.getenv('OFFLINE_THRESHOLD', DEFAULT_OFFLINE_THRESHOLD))
            
            # Try to load from YAML if it exists
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                
                # Update from YAML if available
                if config and isinstance(config, dict):
                    # Temperature settings
                    if 'temperature' in config:
                        temp_config = config['temperature']
                        for key, value in temp_config.items():
                            if hasattr(self.temp_config, key):
                                setattr(self.temp_config, key, value)
                    
                    # General settings
                    if 'general' in config:
                        general = config['general']
                        self.check_interval = general.get('check_interval', self.check_interval)
                        self.offline_threshold = general.get('offline_threshold', self.offline_threshold)
                
                logger.info(f"Loaded configuration from {config_path}")
            else:
                logger.info("No config file found, using environment variables")
        
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            # Fall back to defaults if there's an error
            self.temp_config = TemperatureConfig()
            self.check_interval = DEFAULT_CHECK_INTERVAL
            self.offline_threshold = DEFAULT_OFFLINE_THRESHOLD
    
    def init_clients(self) -> None:
        """Initialize API clients."""
        # InfluxDB client
        try:
            self.influx_url = os.getenv('INFLUX_URL')
            self.influx_token = os.getenv('INFLUX_TOKEN')
            self.influx_org = os.getenv('INFLUX_ORG')
            self.influx_bucket = os.getenv('INFLUX_BUCKET')
            
            if not all([self.influx_url, self.influx_token, self.influx_org, self.influx_bucket]):
                raise ValueError("Missing InfluxDB environment variables")
            
            self.influx_client = InfluxClient(
                url=self.influx_url,
                token=self.influx_token,
                org=self.influx_org,
                bucket=self.influx_bucket
            )
            
            logger.info("InfluxDB client initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing InfluxDB client: {e}")
            raise
        
        # Discord client
        try:
            self.discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
            self.discord_username = os.getenv('DISCORD_USERNAME', 'Influx Monitor')
            self.discord_avatar_url = os.getenv('DISCORD_AVATAR_URL')
            
            if self.discord_webhook_url:
                self.discord_client = DiscordClient(
                    webhook_url=self.discord_webhook_url,
                    username=self.discord_username,
                    avatar_url=self.discord_avatar_url
                )
                logger.info("Discord client initialized successfully")
            else:
                self.discord_client = None
                logger.warning("Discord webhook URL not provided, alerts will not be sent")
        except Exception as e:
            logger.error(f"Error initializing Discord client: {e}")
            self.discord_client = None
        
        # Grafana client (optional)
        try:
            self.grafana_url = os.getenv('GRAFANA_URL')
            self.grafana_api_key = os.getenv('GRAFANA_API_KEY')
            self.grafana_dashboard_uid = os.getenv('GRAFANA_DASHBOARD_UID')
            
            if all([self.grafana_url, self.grafana_api_key, self.grafana_dashboard_uid]):
                refresh_interval = int(os.getenv('GRAFANA_REFRESH_INTERVAL', 300))
                
                self.grafana_client = GrafanaClient(
                    grafana_url=self.grafana_url,
                    api_key=self.grafana_api_key,
                    dashboard_uid=self.grafana_dashboard_uid,
                    refresh_interval=refresh_interval
                )
                
                # Initial configuration fetch
                self.update_config_from_grafana()
                logger.info("Grafana client initialized successfully")
            else:
                self.grafana_client = None
                logger.info("Grafana client not configured, using local configuration only")
        except Exception as e:
            logger.error(f"Error initializing Grafana client: {e}")
            self.grafana_client = None
    
    def update_config_from_grafana(self) -> bool:
        """
        Update configuration from Grafana if available.
        
        Returns:
            True if configuration was updated, False otherwise
        """
        if not self.grafana_client:
            return False
        
        try:
            # Update temperature config
            updated = self.grafana_client.update_temperature_config(self.temp_config)
            
            # Check for general settings
            variables = self.grafana_client.get_variables()
            
            if 'check_interval' in variables:
                new_interval = int(variables['check_interval'])
                if new_interval != self.check_interval:
                    self.check_interval = new_interval
                    logger.info(f"Updated check interval to {new_interval}")
                    updated = True
            
            if 'offline_threshold' in variables:
                new_threshold = int(variables['offline_threshold'])
                if new_threshold != self.offline_threshold:
                    self.offline_threshold = new_threshold
                    logger.info(f"Updated offline threshold to {new_threshold}")
                    updated = True
            
            if updated:
                logger.info("Updated configuration from Grafana")
                
                # Update trackers with new config
                self.sensor_tracker.temp_config = self.temp_config
                self.temp_tracker.temp_config = self.temp_config
            
            return updated
        
        except Exception as e:
            logger.error(f"Error updating configuration from Grafana: {e}")
            return False
    
    def check_raspberry_pi_online(self) -> bool:
        """
        Check if the Raspberry Pi is online by looking for recent data.
        
        Returns:
            True if the Pi is online, False otherwise
        """
        # Only check every few minutes to avoid unnecessary queries
        if (datetime.now() - self.last_online_check).total_seconds() < 180:  # 3 minutes
            return self.pi_online
        
        self.last_online_check = datetime.now()
        
        # Check for recent data
        online_status = self.influx_client.check_for_recent_data(seconds=self.offline_threshold)
        
        # Detect status changes
        if online_status != self.pi_online:
            if self.discord_client:
                self.discord_client.send_raspberry_pi_alert(online_status)
            
            self.pi_online = online_status
        
        return self.pi_online
    
    async def process_temperature_data(self) -> None:
        """Process temperature data and send alerts if needed."""
        # Get recent temperature data
        ds18b20_temps = self.influx_client.get_recent_temperature_data("DS18B20", minutes=15)
        si7021_temps = self.influx_client.get_recent_temperature_data("SI7021", minutes=15)
        
        if not ds18b20_temps:
            logger.warning("No DS18B20 temperature data found")
            return
        
        # Determine sensor state
        new_sensor_state = self.sensor_tracker.determine_state(ds18b20_temps, si7021_temps)
        state_changed = self.sensor_tracker.update_state(new_sensor_state)
        
        # Send sensor state alerts if state changed
        if state_changed and self.discord_client and self.sensor_tracker.state != SensorState.UNKNOWN:
            # Special descriptions for each state
            descriptions = {
                SensorState.CONNECTED: "Temperature sensor is now properly connected and monitoring body temperature.",
                SensorState.DISCONNECTED: "Temperature sensor has been disconnected or removed from body.",
                SensorState.MISPOSITIONED: "Temperature sensor appears to be mispositioned. Please check placement."
            }
            
            # Colors for each state
            colors = {
                SensorState.CONNECTED: DISCORD_COLORS["green"],
                SensorState.DISCONNECTED: DISCORD_COLORS["orange"],
                SensorState.MISPOSITIONED: DISCORD_COLORS["yellow"]
            }
            
            self.discord_client.send_sensor_state_alert(
                state_name=new_sensor_state.name,
                description=descriptions.get(new_sensor_state, ""),
                color=colors.get(new_sensor_state, DISCORD_COLORS["blue"])
            )
        
        # Process temperature state if sensor is connected and not in stabilization mode
        latest_temp = ds18b20_temps[-1]['value']
        
        if new_sensor_state == SensorState.CONNECTED and not self.sensor_tracker.is_in_stabilization_mode():
            # Update temperature state
            state_changed = self.temp_tracker.update_state(latest_temp)
            
            # Send temperature alert if state changed and not first reading
            if state_changed and self.discord_client:
                alert_info = self.temp_tracker.get_alert_info(latest_temp)
                if alert_info:
                    self.discord_client.send_alert(
                        title=alert_info["title"],
                        description=alert_info["description"],
                        color=alert_info["color"]
                    )
    
    async def run(self) -> None:
        """Main monitoring loop."""
        logger.info("Starting influx monitor")
        
        try:
            while True:
                # Periodically refresh config from Grafana
                current_time = time.time()
                if self.grafana_client and (current_time - self.last_grafana_refresh > self.grafana_client.refresh_interval):
                    self.update_config_from_grafana()
                    self.last_grafana_refresh = current_time
                
                # Check if the Raspberry Pi is online
                pi_online = self.check_raspberry_pi_online()
                
                if pi_online:
                    # Process temperature data
                    await self.process_temperature_data()
                
                # Sleep before the next check
                await asyncio.sleep(self.check_interval)
        
        except asyncio.CancelledError:
            logger.info("Influx monitor task cancelled")
        except Exception as e:
            logger.error(f"Error in influx monitor: {e}", exc_info=True)
            # Send emergency alert
            if self.discord_client:
                self.discord_client.send_error_alert(str(e))
            raise