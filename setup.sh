#!/bin/bash

# setup.sh - Setup script for Influx Monitor service
# This script sets up everything needed to run the influx-monitor service
# Usage: Run this script from within the repository directory

echo "Setting up Influx Monitor Service..."

# Define installation paths - automatically use current directory
SCRIPT_DIR   = "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME = "influx-monitor"
INSTALL_DIR  = "$SCRIPT_DIR"  # Use the directory where the script is located
VENV_DIR     = "$INSTALL_DIR/venv"
SERVICE_FILE = "/etc/systemd/system/$SERVICE_NAME.service"
LOG_DIR      = "$INSTALL_DIR/logs"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root or with sudo"
  exit 1
fi

# Display installation paths
echo "Using the following paths:"
echo "  Installation directory: $INSTALL_DIR"
echo "  Virtual environment: $VENV_DIR"
echo "  Log directory: $LOG_DIR"
echo ""

# Install required packages if not already installed
echo "Checking and installing required packages..."
apt-get update
apt-get install -y python3-pip python3-venv

# Create log directory if it doesn't exist
echo "Creating log directory..."
mkdir -p $LOG_DIR

# Create .env file if it doesn't exist
if [ ! -f "$INSTALL_DIR/.env" ]; then
  echo "Creating initial .env file from example..."
  cp $INSTALL_DIR/.env.example $INSTALL_DIR/.env
  echo "Please edit $INSTALL_DIR/.env with your actual configuration"
fi

# Create Python virtual environment and install dependencies
echo "Setting up Python virtual environment..."
python3 -m venv $VENV_DIR
$VENV_DIR/bin/pip install --upgrade pip
$VENV_DIR/bin/pip install -r $INSTALL_DIR/requirements.txt

# Create systemd service file
echo "Creating systemd service..."
cat << EOF > $SERVICE_FILE
[Unit]
Description=Influx Monitor Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/main.py
Restart=on-failure
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# Set proper permissions
echo "Setting permissions..."
OWNER=$(stat -c '%U' "$INSTALL_DIR")
GROUP=$(stat -c '%G' "$INSTALL_DIR")
chown -R $OWNER:$GROUP $INSTALL_DIR
chmod -R 755 $INSTALL_DIR
chmod 640 $INSTALL_DIR/.env
chmod -R 777 $LOG_DIR  # Make log directory writable

# Enable and start the service
echo "Enabling and starting the service..."
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

echo "Setup complete!"
echo "---------------------------------------------------------------------"
echo "The Influx Monitor service has been installed and started."
echo ""
echo "NEXT STEPS:"
echo "1. Edit the .env file with your configuration:"
echo "   sudo nano $INSTALL_DIR/.env"
echo ""
echo "2. Restart the service after editing configuration:"
echo "   sudo systemctl restart $SERVICE_NAME"
echo ""
echo "USEFUL COMMANDS:"
echo "  Check status: sudo systemctl status $SERVICE_NAME"
echo "  View service logs: sudo journalctl -u $SERVICE_NAME -f"
echo "  View application logs: sudo tail -f $LOG_DIR/influx_monitor.log"
echo "---------------------------------------------------------------------"