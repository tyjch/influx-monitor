#!/bin/bash

# setup.sh - Script to set up the Influx Monitor service
# This script installs dependencies and creates a systemd service for the temperature monitor

echo "Setting up Influx Monitor Service..."

# Define installation paths
SERVICE_NAME="influx-monitor"
INSTALL_DIR="/opt/influx-monitor"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
LOG_DIR="$INSTALL_DIR/logs"

# Create installation directory
echo "Creating installation directory..."
sudo mkdir -p $INSTALL_DIR
sudo mkdir -p $LOG_DIR

# Copy service files
echo "Copying service files..."
sudo cp -r ./* $INSTALL_DIR/
sudo cp -n .env.example $INSTALL_DIR/.env 2>/dev/null || true

# Create venv and install dependencies
echo "Setting up Python virtual environment..."
sudo python -m venv $VENV_DIR
sudo $VENV_DIR/bin/pip install --upgrade pip
sudo $VENV_DIR/bin/pip install -r $INSTALL_DIR/requirements.txt

# Create systemd service file
echo "Creating systemd service..."
cat << EOF | sudo tee $SERVICE_FILE > /dev/null
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

# Set permissions
echo "Setting permissions..."
sudo chown -R root:root $INSTALL_DIR
sudo chmod -R 755 $INSTALL_DIR
sudo chmod 640 $INSTALL_DIR/.env
sudo chmod -R 777 $LOG_DIR  # Make log directory writable

# Enable and start the service
echo "Enabling and starting the service..."
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl start $SERVICE_NAME

echo "Setup complete!"
echo "---------------------------------------------------------------------"
echo "The Influx Monitor service has been installed an