import logging
import time
from typing import Callable, List, Optional, Dict, Any

from common.suspension_core.can.can_interface import CanInterface
from common.suspension_core.config.manager import ConfigManager

logger = logging.getLogger(__name__)

class CanReader:
    """
    CAN Reader for the Hardware Bridge Service.
    
    This class handles reading CAN messages from the hardware and
    processing them for use in the Hardware Bridge Service.
    """
    
    def __init__(self, config: Optional[ConfigManager] = None):
        """
        Initialize the CAN Reader.
        
        Args:
            config: Configuration manager (optional)
        """
        self.config = config or ConfigManager()
        self.can_interface = CanInterface(
            channel=self.config.get("can.interface", "can0"),
            baudrate=self.config.get("can.baudrate", 1000000),
            auto_detect_baud=self.config.get("can.auto_detect_baud", True),
            protocol=self.config.get("can.protocol", "eusama")
        )
        self.message_callbacks: List[Callable] = []
        self.connected = False
        self.stats = {
            "messages_received": 0,
            "last_message_time": 0,
            "errors": 0
        }
        
    def connect(self) -> bool:
        """
        Connect to the CAN interface.
        
        Returns:
            True if connection was successful, False otherwise
        """
        try:
            result = self.can_interface.connect()
            if result:
                logger.info(f"Connected to CAN interface {self.can_interface.channel}")
                self.connected = True
                # Register our message callback
                self.can_interface.add_message_callback(self._on_can_message)
            else:
                logger.error(f"Failed to connect to CAN interface {self.can_interface.channel}")
            return result
        except Exception as e:
            logger.error(f"Error connecting to CAN interface: {e}")
            return False
            
    def disconnect(self) -> None:
        """Disconnect from the CAN interface."""
        try:
            if self.connected:
                self.can_interface.shutdown()
                logger.info("Disconnected from CAN interface")
                self.connected = False
        except Exception as e:
            logger.error(f"Error disconnecting from CAN interface: {e}")
            
    def add_message_callback(self, callback: Callable) -> None:
        """
        Add a callback for CAN messages.
        
        Args:
            callback: Callback function that takes a CAN message as argument
        """
        if callback not in self.message_callbacks:
            self.message_callbacks.append(callback)
            logger.debug(f"Added CAN message callback: {callback.__name__}")
            
    def remove_message_callback(self, callback: Callable) -> None:
        """
        Remove a callback for CAN messages.
        
        Args:
            callback: Callback function to remove
        """
        if callback in self.message_callbacks:
            self.message_callbacks.remove(callback)
            logger.debug(f"Removed CAN message callback: {callback.__name__}")
            
    def _on_can_message(self, msg) -> None:
        """
        Handle incoming CAN messages.
        
        Args:
            msg: CAN message
        """
        try:
            # Update statistics
            self.stats["messages_received"] += 1
            self.stats["last_message_time"] = time.time()
            
            # Call all registered callbacks
            for callback in self.message_callbacks:
                try:
                    callback(msg)
                except Exception as e:
                    logger.error(f"Error in CAN message callback {callback.__name__}: {e}")
                    self.stats["errors"] += 1
        except Exception as e:
            logger.error(f"Error handling CAN message: {e}")
            self.stats["errors"] += 1
            
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the CAN reader.
        
        Returns:
            Dictionary with status information
        """
        return {
            "connected": self.connected,
            "interface": self.can_interface.channel if self.connected else None,
            "baudrate": self.can_interface.current_baudrate if self.connected else None,
            "messages_received": self.stats["messages_received"],
            "last_message_time": self.stats["last_message_time"],
            "errors": self.stats["errors"]
        }
        
    def send_message(self, arbitration_id: int, data: bytes, is_extended_id: bool = False) -> bool:
        """
        Send a CAN message.
        
        Args:
            arbitration_id: CAN ID
            data: CAN data
            is_extended_id: Whether to use extended ID format
            
        Returns:
            True if sending was successful, False otherwise
        """
        if not self.connected:
            logger.error("Cannot send message: Not connected to CAN interface")
            return False
            
        try:
            return self.can_interface.send_message(arbitration_id, data, is_extended_id)
        except Exception as e:
            logger.error(f"Error sending CAN message: {e}")
            self.stats["errors"] += 1
            return False