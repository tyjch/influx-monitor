import os
import sys
import asyncio
from dotenv import load_dotenv
from loguru import logger
from monitor.influx_monitor import InfluxMonitor

# Configure Loguru logger
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE  = os.getenv("LOG_FILE", "logs/influx_monitor.log")

# Ensure log directory exists
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# Configure logger
logger.remove() # Remove default handler
logger.add(sys.stderr, level=LOG_LEVEL)
logger.add(LOG_FILE, rotation="10 MB", retention="1 week", level=LOG_LEVEL)

async def main():
    """Main entry point for the influx monitor service."""
    # Load environment variables
    load_dotenv()
    
    # Create and run monitor
    try:
        monitor = InfluxMonitor()
        await monitor.run()
    except Exception as e:
        logger.error(f"Error in main process: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Influx Monitor stopped by user")