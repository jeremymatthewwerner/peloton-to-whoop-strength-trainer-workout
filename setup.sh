#!/bin/bash

# Peloton-to-Whoop Setup Script

# Exit on error
set -e

echo "Setting up Peloton-to-Whoop Strength Trainer Integration..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment already exists."
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create config file if it doesn't exist
if [ ! -f "config.ini" ]; then
    echo "Creating config.ini from template..."
    cp config.example.ini config.ini
    echo "Please edit config.ini with your Peloton and Whoop credentials."
else
    echo "Config file already exists."
fi

echo ""
echo "Setup complete! Follow these steps to use the integration:"
echo "1. Edit config.ini with your Peloton and Whoop credentials"
echo "2. Activate the virtual environment: source venv/bin/activate"
echo "3. Run the integration: python src/main.py"
echo ""
