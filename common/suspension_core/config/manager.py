"""
Configuration Manager for Fahrwerkstester Common Library

This module provides a centralized configuration management system for the
Fahrwerkstester applications. It handles loading, validating, and accessing
configuration settings from various sources.
"""

import os
import json
import yaml
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union


class ConfigManager:
    """
    Singleton configuration manager that handles loading, validating, and
    accessing configuration settings for Fahrwerkstester applications.
    
    This class provides a centralized way to manage configuration across
    different components of the system. It supports loading from YAML files,
    environment variables, and provides defaults when needed.
    
    Attributes:
        config_path (str): Path to the configuration file
        config (dict): The loaded configuration dictionary
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        """Implement singleton pattern"""
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the ConfigManager.
        
        Args:
            config_path: Path to the configuration file. If None, uses default locations.
        """
        # Only initialize once (singleton pattern)
        if hasattr(self, 'initialized') and self.initialized:
            return
            
        self.logger = logging.getLogger(__name__)
        
        # Set default config path if not provided
        if config_path is None:
            # Try to find config in standard locations
            possible_paths = [
                os.path.join(os.getcwd(), 'config.yaml'),
                os.path.join(os.getcwd(), 'config.yml'),
                os.path.expanduser('~/.fahrwerkstester/config.yaml'),
                '/etc/fahrwerkstester/config.yaml',
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    config_path = path
                    break
        
        self.config_path = config_path
        self.config = self._get_default_config()
        
        # Load configuration from file if it exists
        if config_path and os.path.exists(config_path):
            self._load_config()
        
        # Load environment variables
        self._load_env_vars()
        
        # Validate the configuration
        self._validate_config()
        
        self.initialized = True
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        Get the default configuration.
        
        Returns:
            Dict containing the default configuration
        """
        return {
            "mqtt": {
                "broker": "localhost",
                "port": 1883,
                "username": None,
                "password": None,
                "client_id": None,
                "topics": {
                    "command": "fahrwerkstester/command",
                    "status": "fahrwerkstester/status",
                    "measurement": "fahrwerkstester/measurement",
                    "raw_data": "fahrwerkstester/raw_data",
                    "motor_status": "fahrwerkstester/motor_status",
                    "gui_command": "fahrwerkstester/gui_command"
                }
            },
            "can": {
                "interface_type": "socketcan",  # socketcan, kvaser, vector, etc.
                "channel": "can0",
                "bitrate": 500000,
                "receive_own_messages": False,
                "fd": False,
                "data_bitrate": None
            },
            "logging": {
                "level": "INFO",
                "file": None,
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            },
            "test": {
                "default_frequency": 1.0,
                "default_amplitude": 10.0,
                "default_phase_shift": 0.0,
                "max_frequency": 10.0,
                "max_amplitude": 50.0,
                "measurement_interval": 0.1,  # seconds
                "processing": {
                    "window_size": 100,  # samples
                    "overlap": 50,  # samples
                    "method": "phase_shift"  # phase_shift, fft, etc.
                }
            },
            "hardware": {
                "positions": ["front_left", "front_right", "rear_left", "rear_right"],
                "calibration": {
                    "front_left": {"offset": 0.0, "scale": 1.0},
                    "front_right": {"offset": 0.0, "scale": 1.0},
                    "rear_left": {"offset": 0.0, "scale": 1.0},
                    "rear_right": {"offset": 0.0, "scale": 1.0}
                }
            },
            "gui": {
                "theme": "light",
                "language": "en",
                "update_interval": 100,  # milliseconds
                "plot_history": 1000  # samples
            }
        }
    
    def _load_config(self):
        """Load configuration from file."""
        try:
            with open(self.config_path, 'r') as f:
                if self.config_path.endswith(('.yaml', '.yml')):
                    loaded_config = yaml.safe_load(f)
                elif self.config_path.endswith('.json'):
                    loaded_config = json.load(f)
                else:
                    self.logger.warning(f"Unsupported config file format: {self.config_path}")
                    return
                
                if loaded_config:
                    # Update the default config with loaded values
                    self.config = self._update_nested_dict(self.config, loaded_config)
                    self.logger.info(f"Loaded configuration from {self.config_path}")
        except Exception as e:
            self.logger.error(f"Error loading configuration from {self.config_path}: {e}")
    
    def _load_env_vars(self):
        """Load configuration from environment variables."""
        # Look for environment variables with prefix FAHRWERKSTESTER_
        prefix = "FAHRWERKSTESTER_"
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Remove prefix and split by underscore to get nested keys
                config_path = key[len(prefix):].lower().split('_')
                
                # Try to parse the value (bool, int, float, etc.)
                parsed_value = value
                try:
                    # Try as JSON first
                    parsed_value = json.loads(value)
                except json.JSONDecodeError:
                    # Then try as individual types
                    if value.lower() in ('true', 'yes', 'y', '1'):
                        parsed_value = True
                    elif value.lower() in ('false', 'no', 'n', '0'):
                        parsed_value = False
                    elif value.isdigit():
                        parsed_value = int(value)
                    else:
                        try:
                            parsed_value = float(value)
                        except ValueError:
                            # Keep as string if all else fails
                            pass
                
                # Set the value in the config
                self.set(config_path, parsed_value)
                self.logger.debug(f"Set config {'.'.join(config_path)} from environment variable {key}")
    
    def _validate_config(self):
        """Validate the configuration and set defaults for missing values."""
        # Ensure required sections exist
        required_sections = ["mqtt", "logging"]
        for section in required_sections:
            if section not in self.config:
                self.config[section] = self._get_default_config()[section]
                self.logger.warning(f"Missing required config section '{section}'. Using defaults.")
        
        # Validate MQTT configuration
        mqtt_config = self.config.get("mqtt", {})
        if not mqtt_config.get("broker"):
            mqtt_config["broker"] = "localhost"
            self.logger.warning("MQTT broker not specified. Using 'localhost'.")
        
        if not mqtt_config.get("port"):
            mqtt_config["port"] = 1883
            self.logger.warning("MQTT port not specified. Using default port 1883.")
        
        # Ensure topics are defined
        if "topics" not in mqtt_config:
            mqtt_config["topics"] = self._get_default_config()["mqtt"]["topics"]
            self.logger.warning("MQTT topics not specified. Using defaults.")
    
    def get(self, path: Union[str, list], default: Any = None) -> Any:
        """
        Get a configuration value by path.
        
        Args:
            path: Dot-notation string or list of keys
            default: Default value if path doesn't exist
            
        Returns:
            The configuration value or default
        """
        if isinstance(path, str):
            path = path.split('.')
        
        current = self.config
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        
        return current
    
    def set(self, path: Union[str, list], value: Any, save: bool = False):
        """
        Set a configuration value by path.
        
        Args:
            path: Dot-notation string or list of keys
            value: Value to set
            save: Whether to save the configuration to file
        """
        if isinstance(path, str):
            path = path.split('.')
        
        current = self.config
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[path[-1]] = value
        
        if save:
            self.save_config()
    
    def save_config(self):
        """Save the configuration to file."""
        if not self.config_path:
            self.logger.warning("Cannot save configuration: No config path specified")
            return
        
        try:
            # Ensure directory exists
            config_dir = os.path.dirname(self.config_path)
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir)
            
            with open(self.config_path, 'w') as f:
                if self.config_path.endswith(('.yaml', '.yml')):
                    yaml.dump(self.config, f, default_flow_style=False)
                elif self.config_path.endswith('.json'):
                    json.dump(self.config, f, indent=2)
                else:
                    self.logger.warning(f"Unsupported config file format: {self.config_path}")
                    return
                
            self.logger.info(f"Saved configuration to {self.config_path}")
        except Exception as e:
            self.logger.error(f"Error saving configuration to {self.config_path}: {e}")
    
    def _update_nested_dict(self, d: dict, u: dict) -> dict:
        """
        Update a nested dictionary with another dictionary.
        
        Args:
            d: Base dictionary
            u: Dictionary with updates
            
        Returns:
            Updated dictionary
        """
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                d[k] = self._update_nested_dict(d[k], v)
            else:
                d[k] = v
        return d
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Get the entire configuration as a dictionary.
        
        Returns:
            The configuration dictionary
        """
        return self.config.copy()
    
    def reset_to_defaults(self, save: bool = False):
        """
        Reset the configuration to defaults.
        
        Args:
            save: Whether to save the configuration to file
        """
        self.config = self._get_default_config()
        if save:
            self.save_config()