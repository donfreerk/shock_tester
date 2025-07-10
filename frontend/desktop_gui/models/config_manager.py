"""
Enhanced Configuration Manager for suspension tester.

Responsibility: Configuration management with intelligent broker discovery.
Extracted from the original monolithic GUI.
"""

import time
import socket
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class SuspensionBrokerInfo:
    """Information about a discovered suspension MQTT broker."""
    
    def __init__(self, ip: str, hostname: str = None, confidence: float = 0.0, 
                 suspension_topics: List[str] = None, response_time: float = 0.0):
        self.ip = ip
        self.hostname = hostname or f"host-{ip}"
        self.confidence = confidence
        self.suspension_topics = suspension_topics or []
        self.response_time = response_time


class EnhancedConfigManager:
    """
    Enhanced Configuration Manager with intelligent MQTT broker discovery.
    
    Features:
    - Automatic broker discovery with caching
    - Fallback broker management
    - Configuration persistence
    - Network testing and validation
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config = self._get_default_config()
        
        # Discovery state
        self._discovered_brokers: List[SuspensionBrokerInfo] = []
        self._last_discovery_time = 0
        self._discovery_cache_timeout = 300  # 5 minutes
        
        # Broker cache
        self._mqtt_broker_cache = []
        
        # Smart discovery (if available)
        self._smart_discovery = None
        self._init_smart_discovery()
        
        # Load configuration
        self._load_configuration()
        
        logger.info("EnhancedConfigManager initialized")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "mqtt": {
                "broker": "auto",
                "port": 1883,
                "username": None,
                "password": None,
                "auto_discovery": True,
                "fallback_brokers": [
                    "192.168.0.249",  # Current Pi IP
                    "192.168.0.100",
                    "192.168.1.100", 
                    "localhost"
                ]
            },
            "network": {
                "discovery_timeout": 5.0,
                "cache_timeout": 300,
                "ping_timeout": 2.0
            },
            "egea": {
                "phase_shift_threshold": 35.0,
                "min_frequency": 6.0,
                "max_frequency": 25.0,
                "test_duration": 30.0
            },
            "gui": {
                "update_rate_ms": 100,
                "max_chart_points": 500,
                "enable_advanced_charts": True
            },
            "logging": {
                "level": "INFO",
                "file_logging": False
            }
        }
    
    def _init_smart_discovery(self):
        """Initialize smart discovery if available."""
        try:
            from smart_suspension_discovery import SmartSuspensionDiscovery
            self._smart_discovery = SmartSuspensionDiscovery(timeout=8.0, max_workers=8)
            logger.info("Smart suspension discovery available")
        except ImportError:
            logger.info("Smart suspension discovery not available")
    
    def _load_configuration(self):
        """Load configuration from file."""
        if not self.config_path:
            return
        
        config_file = Path(self.config_path)
        if not config_file.exists():
            logger.info(f"Config file not found: {self.config_path}")
            return
        
        try:
            import yaml
            with open(config_file, 'r') as f:
                loaded_config = yaml.safe_load(f)
                if loaded_config:
                    self._merge_config(self.config, loaded_config)
                    logger.info(f"Configuration loaded from {self.config_path}")
        except ImportError:
            logger.warning("PyYAML not available - using default configuration")
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
    
    def _merge_config(self, target: Dict[str, Any], source: Dict[str, Any]):
        """Recursively merge configuration dictionaries."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._merge_config(target[key], value)
            else:
                target[key] = value
    
    def save_configuration(self) -> bool:
        """Save current configuration to file."""
        if not self.config_path:
            return False
        
        try:
            import yaml
            config_file = Path(self.config_path)
            config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_file, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False, indent=2)
            
            logger.info(f"Configuration saved to {self.config_path}")
            return True
            
        except ImportError:
            logger.warning("PyYAML not available - cannot save configuration")
            return False
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False
    
    # =================================================================
    # MQTT Broker Discovery
    # =================================================================
    
    def get_mqtt_broker(self, force_discovery: bool = False) -> str:
        """
        Get best available MQTT broker.
        
        Args:
            force_discovery: Force new discovery even if cache is valid
            
        Returns:
            IP address of best broker
        """
        if force_discovery or not self._mqtt_broker_cache:
            self._refresh_broker_list()
        
        # Test cached brokers
        for broker in self._mqtt_broker_cache:
            if self._test_mqtt_broker(broker):
                logger.debug(f"Using MQTT broker: {broker}")
                return broker
        
        # Fallback to configured brokers
        fallback_brokers = self.get("mqtt.fallback_brokers", ["localhost"])
        for broker in fallback_brokers:
            if self._test_mqtt_broker(broker):
                logger.info(f"Using fallback broker: {broker}")
                return broker
        
        # Last resort
        logger.warning("No MQTT broker found, using localhost")
        return "localhost"
    
    def _refresh_broker_list(self):
        """Refresh broker list with discovery."""
        current_time = time.time()
        
        # Check cache timeout
        if (current_time - self._last_discovery_time) < self._discovery_cache_timeout:
            if self._mqtt_broker_cache:
                return
        
        logger.info("Starting MQTT broker discovery...")
        
        # Smart discovery if available
        if self._smart_discovery:
            try:
                brokers = self._smart_discovery.discover_suspension_brokers()
                self._discovered_brokers = brokers
                
                # Update cache with discovered brokers (sorted by confidence)
                self._mqtt_broker_cache = [
                    broker.ip for broker in brokers 
                    if broker.confidence > 0.3
                ]
                
                logger.info(f"Smart discovery found {len(brokers)} suspension brokers")
                
            except Exception as e:
                logger.warning(f"Smart discovery failed: {e}")
                self._mqtt_broker_cache = []
        else:
            # Simple network scan as fallback
            self._mqtt_broker_cache = self._simple_broker_scan()
        
        # Add fallback brokers
        fallback_brokers = self.get("mqtt.fallback_brokers", [])
        for broker in fallback_brokers:
            if broker not in self._mqtt_broker_cache:
                self._mqtt_broker_cache.append(broker)
        
        self._last_discovery_time = current_time
        logger.info(f"Broker discovery complete: {len(self._mqtt_broker_cache)} brokers")
    
    def _simple_broker_scan(self) -> List[str]:
        """Simple network scan for MQTT brokers."""
        brokers = []
        
        # Scan common IP ranges
        base_ips = [
            "192.168.0",
            "192.168.1", 
            "10.0.0",
            "172.16.0"
        ]
        
        common_hosts = [1, 100, 249, 250]  # Common MQTT broker IPs
        
        for base_ip in base_ips:
            for host in common_hosts:
                ip = f"{base_ip}.{host}"
                if self._test_mqtt_broker(ip, timeout=1.0):
                    brokers.append(ip)
                    if len(brokers) >= 5:  # Limit scan
                        break
            if len(brokers) >= 5:
                break
        
        return brokers
    
    def _test_mqtt_broker(self, broker: str, timeout: float = 2.0) -> bool:
        """Test if MQTT broker is reachable."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((broker, self.get("mqtt.port", 1883)))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def force_broker_discovery(self) -> str:
        """Force new broker discovery."""
        self._mqtt_broker_cache.clear()
        self._last_discovery_time = 0
        return self.get_mqtt_broker(force_discovery=True)
    
    def add_fallback_broker(self, broker: str):
        """Add broker to fallback list."""
        fallbacks = self.get("mqtt.fallback_brokers", [])
        if broker not in fallbacks:
            fallbacks.insert(0, broker)  # Add to front
            self.set("mqtt.fallback_brokers", fallbacks)
            logger.info(f"Added fallback broker: {broker}")
    
    def get_discovered_devices(self) -> List[SuspensionBrokerInfo]:
        """Get list of discovered suspension brokers."""
        return self._discovered_brokers.copy()
    
    # =================================================================
    # Configuration Access
    # =================================================================
    
    def get(self, path: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-separated path.
        
        Args:
            path: Configuration path (e.g., "mqtt.broker")
            default: Default value if path not found
            
        Returns:
            Configuration value or default
        """
        keys = path.split('.')
        current = self.config
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        
        return current
    
    def set(self, path: str, value: Any):
        """
        Set configuration value by dot-separated path.
        
        Args:
            path: Configuration path (e.g., "mqtt.broker")
            value: Value to set
        """
        keys = path.split('.')
        current = self.config
        
        # Navigate to parent
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Set final value
        current[keys[-1]] = value
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get entire configuration section.
        
        Args:
            section: Section name (e.g., "mqtt")
            
        Returns:
            Configuration section or empty dict
        """
        return self.get(section, {})
    
    def update_section(self, section: str, values: Dict[str, Any]):
        """
        Update entire configuration section.
        
        Args:
            section: Section name
            values: New values for section
        """
        if section not in self.config:
            self.config[section] = {}
        
        self.config[section].update(values)
    
    # =================================================================
    # Network Utilities
    # =================================================================
    
    def get_local_ip(self) -> str:
        """Get local IP address."""
        try:
            # Connect to a remote address to determine local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"
    
    def get_network_info(self) -> Dict[str, Any]:
        """Get network information for diagnostics."""
        return {
            "local_ip": self.get_local_ip(),
            "discovered_brokers": len(self._discovered_brokers),
            "cached_brokers": len(self._mqtt_broker_cache),
            "last_discovery": self._last_discovery_time,
            "smart_discovery_available": self._smart_discovery is not None
        }
    
    def test_network_connectivity(self) -> Dict[str, Any]:
        """Test network connectivity to various services."""
        results = {}
        
        # Test internet connectivity
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            result = sock.connect_ex(("8.8.8.8", 53))
            sock.close()
            results["internet"] = result == 0
        except Exception:
            results["internet"] = False
        
        # Test local network
        local_ip = self.get_local_ip()
        if local_ip != "127.0.0.1":
            # Test gateway (usually .1)
            gateway_ip = ".".join(local_ip.split(".")[:-1]) + ".1"
            results["gateway"] = self._test_mqtt_broker(gateway_ip, timeout=1.0)
        else:
            results["gateway"] = False
        
        # Test MQTT brokers
        fallback_brokers = self.get("mqtt.fallback_brokers", [])
        results["mqtt_brokers"] = {}
        for broker in fallback_brokers:
            results["mqtt_brokers"][broker] = self._test_mqtt_broker(broker)
        
        return results
    
    # =================================================================
    # Diagnostics and Status
    # =================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive configuration and discovery status."""
        return {
            "config_file": self.config_path,
            "config_loaded": self.config_path and Path(self.config_path).exists(),
            "smart_discovery": self._smart_discovery is not None,
            "discovered_brokers": len(self._discovered_brokers),
            "cached_brokers": len(self._mqtt_broker_cache),
            "last_discovery_age": time.time() - self._last_discovery_time,
            "network_info": self.get_network_info(),
            "current_broker": self.get_mqtt_broker() if self._mqtt_broker_cache else None
        }
    
    def export_config(self) -> str:
        """Export current configuration as YAML string."""
        try:
            import yaml
            return yaml.dump(self.config, default_flow_style=False, indent=2)
        except ImportError:
            import json
            return json.dumps(self.config, indent=2)
    
    def validate_config(self) -> List[str]:
        """Validate configuration and return list of issues."""
        issues = []
        
        # Check required sections
        required_sections = ["mqtt", "egea", "gui"]
        for section in required_sections:
            if section not in self.config:
                issues.append(f"Missing required section: {section}")
        
        # Validate MQTT config
        mqtt_config = self.get_section("mqtt")
        if not mqtt_config.get("fallback_brokers"):
            issues.append("No fallback MQTT brokers configured")
        
        port = mqtt_config.get("port", 1883)
        if not isinstance(port, int) or not (1 <= port <= 65535):
            issues.append(f"Invalid MQTT port: {port}")
        
        # Validate EGEA config
        egea_config = self.get_section("egea")
        threshold = egea_config.get("phase_shift_threshold", 35.0)
        if not isinstance(threshold, (int, float)) or threshold <= 0:
            issues.append(f"Invalid phase shift threshold: {threshold}")
        
        return issues
