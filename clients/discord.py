import json
import requests
from loguru import logger
from datetime import datetime
from typing import Dict, Any, Optional


class DiscordClient:
    
    def __init__(self, webhook_url: str, username: str = "Influx Monitor", avatar_url: Optional[str] = None):
        """
        Initialize the Discord client.
        
        Args:
            webhook_url: Discord webhook URL
            username: Username to display for the webhook
            avatar_url: Avatar URL for the webhook
        """
        self.webhook_url = webhook_url
        self.username = username
        self.avatar_url = avatar_url
    
    def send_alert(self, title: str, description: str, color: int) -> bool:
        """
        Send an alert to Discord.
        
        Args:
            title: The alert title
            description: The alert description
            color: The color for the Discord embed
            
        Returns:
            True if successful, False otherwise
        """
        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured. Cannot send alert.")
            return False
        
        try:
            data = {
                "username": self.username,
                "embeds": [{
                    "title": title,
                    "description": description,
                    "color": color,
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }
            
            if self.avatar_url:
                data["avatar_url"] = self.avatar_url
            
            response = requests.post(
                self.webhook_url,
                data=json.dumps(data),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 204:
                logger.info("Discord alert sent: %s", title)
                return True
            else:
                logger.error("Failed to send Discord alert: %s", response.text)
                return False
                
        except Exception as e:
            logger.error("Error sending Discord alert: %s", e)
            return False
    
    def send_sensor_state_alert(self, state_name: str, description: str, color: int) -> bool:
        """
        Send a sensor state alert to Discord.
        
        Args:
            state_name: Name of the sensor state
            description: Additional information
            color: The color for the Discord embed
            
        Returns:
            True if successful, False otherwise
        """
        return self.send_alert(
            title=f"Sensor {state_name}",
            description=description,
            color=color
        )
    
    def send_temperature_alert(self, state_name: str, temperature: float, description: str, color: int) -> bool:
        """
        Send a temperature alert to Discord.
        
        Args:
            state_name: Name of the temperature state
            temperature: Current temperature value
            description: Additional information
            color: The color for the Discord embed
            
        Returns:
            True if successful, False otherwise
        """
        return self.send_alert(
            title=f"Temperature is {state_name}",
            description=description,
            color=color
        )
    
    def send_raspberry_pi_alert(self, is_online: bool) -> bool:
        """
        Send a Raspberry Pi online/offline alert to Discord.
        
        Args:
            is_online: Whether the Pi is online
            
        Returns:
            True if successful, False otherwise
        """
        if is_online:
            return self.send_alert(
                title="Raspberry Pi is ONLINE",
                description="The monitoring system is now sending data.",
                color=0x00FF00  # Green
            )
        else:
            return self.send_alert(
                title="Raspberry Pi is OFFLINE",
                description="No data received in the last few minutes!",
                color=0xFF0000  # Red
            )
    
    def send_error_alert(self, error: str) -> bool:
        """
        Send an error alert to Discord.
        
        Args:
            error: Error message
            
        Returns:
            True if successful, False otherwise
        """
        return self.send_alert(
            title="Monitor Error",
            description=f"The temperature monitoring service encountered an error: {error}",
            color=0xFF0000  # Red
        )