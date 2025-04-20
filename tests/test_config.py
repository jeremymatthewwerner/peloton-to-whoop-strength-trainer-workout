"""
Tests for the config manager module.
"""

import os
import pytest
import configparser
from pathlib import Path
import tempfile
from src.config import ConfigManager

def test_config_load():
    """Test loading a valid configuration file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write("""
[peloton]
username = test_user
password = test_password

[whoop]
email = test@example.com
password = test_password

[settings]
lookback_days = 30
time_threshold_minutes = 30
        """)
        temp_file.flush()
        
        config = ConfigManager(temp_file.name)
        peloton_creds = config.get_peloton_credentials()
        whoop_creds = config.get_whoop_credentials()
        settings = config.get_settings()
        
        assert peloton_creds['username'] == 'test_user'
        assert peloton_creds['password'] == 'test_password'
        assert whoop_creds['email'] == 'test@example.com'
        assert whoop_creds['password'] == 'test_password'
        assert settings['lookback_days'] == 30
        assert settings['time_threshold_minutes'] == 30
    
    os.unlink(temp_file.name)

def test_config_whoop_api_key():
    """Test loading a configuration with Whoop API key."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write("""
[peloton]
username = test_user
password = test_password

[whoop]
api_key = test_api_key

[settings]
lookback_days = 30
time_threshold_minutes = 30
        """)
        temp_file.flush()
        
        config = ConfigManager(temp_file.name)
        whoop_creds = config.get_whoop_credentials()
        
        assert 'api_key' in whoop_creds
        assert whoop_creds['api_key'] == 'test_api_key'
    
    os.unlink(temp_file.name)

def test_missing_config():
    """Test behavior when config file is missing."""
    with pytest.raises(FileNotFoundError):
        ConfigManager('nonexistent_file.ini')

def test_invalid_config():
    """Test behavior with invalid configuration."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write("""
[peloton]
username = test_user
# Missing password

[whoop]
email = test@example.com
password = test_password

[settings]
lookback_days = 30
time_threshold_minutes = 30
        """)
        temp_file.flush()
        
        with pytest.raises(ValueError):
            ConfigManager(temp_file.name)
    
    os.unlink(temp_file.name)

def test_invalid_settings():
    """Test behavior with invalid settings."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write("""
[peloton]
username = test_user
password = test_password

[whoop]
email = test@example.com
password = test_password

[settings]
lookback_days = not_a_number
time_threshold_minutes = 30
        """)
        temp_file.flush()
        
        with pytest.raises(ValueError):
            ConfigManager(temp_file.name)
    
    os.unlink(temp_file.name)
