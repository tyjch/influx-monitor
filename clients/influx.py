from loguru import logger
from typing import Dict, Any, List, Optional
from datetime import datetime
from influxdb_client import InfluxDBClient

class InfluxClient:

    def __init__(self, url: str, token: str, org: str, bucket: str):
        """
        Initialize the InfluxDB client.
        
        Args:
            url: InfluxDB URL
            token: InfluxDB API token
            org: InfluxDB organization
            bucket: InfluxDB bucket
        """
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        
        # Initialize client
        self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
        self.query_api = self.client.query_api()
        logger.info("InfluxDB client initialized successfully")
    
    def get_recent_temperature_data(self, sensor_name: str, minutes: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent temperature data from InfluxDB.
        
        Args:
            sensor_name: Name of the sensor to query
            minutes: Number of minutes of data to retrieve
            
        Returns:
            List of temperature readings with timestamps
        """
        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -{minutes}m)
          |> filter(fn: (r) => r["_measurement"] == "{sensor_name}")
          |> filter(fn: (r) => r["dimension"] == "temperature")
          |> filter(fn: (r) => r["_field"] == "mean")
          |> yield(name: "mean")
        '''
        
        try:
            result = self.query_api.query(query)
            readings = []
            
            for table in result:
                for record in table.records:
                    readings.append({
                        'time': record.get_time(),
                        'value': record.get_value(),
                        'sensor': sensor_name
                    })
            
            readings.sort(key=lambda x: x['time'])
            return readings
        
        except Exception as e:
            logger.error(f"Error querying InfluxDB: {e}")
            return []
    
    def check_for_recent_data(self, seconds: int = 300) -> bool:
        """
        Check if there is any recent data in InfluxDB.
        
        Args:
            seconds: Number of seconds to check for data
            
        Returns:
            True if recent data exists, False otherwise
        """
        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -{seconds}s)
          |> filter(fn: (r) => r["_field"] == "mean")
          |> count()
          |> yield(name: "count")
        '''
        
        try:
            result = self.query_api.query(query)
            
            # If we have any data points, return True
            count = 0
            for table in result:
                for record in table.records:
                    count += record.get_value()
            
            return count > 0
        
        except Exception as e:
            logger.error(f"Error checking for recent data: {e}")
            return False