@echo off
REM Peloton-to-Whoop Setup Script for Windows

echo Setting up Peloton-to-Whoop Strength Trainer Integration...

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
) else (
    echo Virtual environment already exists.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install requirements
echo Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt

REM Create config file if it doesn't exist
if not exist "config.ini" (
    echo Creating config.ini from template...
    copy config.example.ini config.ini
    echo Please edit config.ini with your Peloton and Whoop credentials.
) else (
    echo Config file already exists.
)

echo.
echo Setup complete! Follow these steps to use the integration:
echo 1. Edit config.ini with your Peloton and Whoop credentials
echo 2. Activate the virtual environment: venv\Scripts\activate
echo 3. Run the integration: python src\main.py
echo.
