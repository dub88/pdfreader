#!/bin/bash
cd "$(dirname "$0")"

echo "Setting up PDF Speaker..."

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed or not in PATH."
    echo "Please install Python 3 from https://www.python.org/downloads/macos/"
    read -p "Press Enter to exit..."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate and install/update dependencies
source venv/bin/activate
echo "Installing dependencies..."
pip install -r requirements.txt --quiet --disable-pip-version-check

# Run the app
echo "Launching App..."
python3 main.py
