"""
Configuration manager for the Peloton-to-Whoop integration.
Handles loading and validation of credentials and settings.
"""

import os
import configparser
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages configuration and credentials for the Peloton-to-Whoop integration."""
    
    def __init__(self, config_path=None):
        """
        Initialize the config manager.
        
        Args:
            config_path: Path to the config file. If None, uses 'config.ini' in the project root.
        """
        self.config = configparser.ConfigParser()
        
        if config_path is None:
            # Default to config.ini in the project root
            self.config_path = Path(__file__).parent.parent / 'config.ini'
        else:
            self.config_path = Path(config_path)
        
        self._load_config()
    
    def _load_config(self):
        """Load the configuration file."""
        if not self.config_path.exists():
            logger.error(f"Config file not found: {self.config_path}")
            raise FileNotFoundError(f"Config file not found: {self.config_path}. "
                                   f"Please copy config.example.ini to config.ini and fill in your credentials.")
        
        self.config.read(self.config_path)
        self._validate_config()
    
    def _validate_config(self):
        """Validate that all required config sections and keys are present."""
        required_sections = ['peloton', 'whoop', 'settings']
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Missing required config section: {section}")
        
        # Validate Peloton credentials
        if ('username' not in self.config['peloton'] or 'password' not in self.config['peloton']):
            raise ValueError("Peloton credentials incomplete. Please provide both username and password.")
        
        # Validate Whoop credentials - either email+password or api_key
        if ('email' not in self.config['whoop'] or 'password' not in self.config['whoop']) and 'api_key' not in self.config['whoop']:
            raise ValueError("Whoop credentials incomplete. Please provide either email+password or api_key.")
        
        # Validate settings
        required_settings = ['lookback_days', 'time_threshold_minutes']
        for setting in required_settings:
            if setting not in self.config['settings']:
                raise ValueError(f"Missing required setting: {setting}")
            
            # Validate numeric settings
            try:
                int(self.config['settings'][setting])
            except ValueError:
                raise ValueError(f"Setting {setting} must be a number.")
    
    def get_peloton_credentials(self):
        """
        Get Peloton credentials.
        
        Returns:
            dict: Dictionary containing Peloton username and password.
        """
        return {
            'username': self.config['peloton']['username'],
            'password': self.config['peloton']['password']
        }
    
    def get_whoop_credentials(self):
        """
        Get Whoop credentials.
        
        Returns:
            dict: Dictionary containing Whoop credentials (either email+password or api_key).
        """
        if 'api_key' in self.config['whoop'] and self.config['whoop']['api_key']:
            return {'api_key': self.config['whoop']['api_key']}
        else:
            return {
                'email': self.config['whoop']['email'],
                'password': self.config['whoop']['password']
            }
    
    def get_settings(self):
        """
        Get application settings.
        
        Returns:
            dict: Dictionary containing application settings.
        """
        return {
            'lookback_days': int(self.config['settings']['lookback_days']),
            'time_threshold_minutes': int(self.config['settings']['time_threshold_minutes'])
        }
