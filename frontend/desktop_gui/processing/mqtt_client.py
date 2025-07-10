"""
MQTT Client for suspension tester GUI.

Responsibility: Handle MQTT communication with automatic reconnection
and robust error handling.
"""

import time
import json
import logging
from typing import Optional, Callable, Any, Dict
import threading

logger = logging.getLogger(__name__)

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    logger.error("paho-mqtt not available - MQTT functionality disabled")


class SimpleMqttClient:
    """
    Simplified MQTT client with automatic reconnection and error handling.
    
    Features:
    - Automatic reconnection on connection loss
    - Thread-safe message handling
    - JSON serialization/deserialization
    - Connection status monitoring
    """
    
    def __init__(self, broker: str, port: int = 1883, client_id: Optional[str] = None):
        if not MQTT_AVAILABLE:
            raise RuntimeError("paho-mqtt not available")
        
        self.broker = broker
        self.port = port
        self.client_id = client_id or f"suspension_gui_{int(time.time())}"
        
        # Connection state
        self.connected = False
        self.connecting = False
        self._reconnect_enabled = True
        self._reconnect_delay = 5.0  # seconds
        
        # Message handling
        self.message_callback: Optional[Callable] = None
        self._subscribed_topics = set()
        
        # Threading
        self._lock = threading.RLock()
        self._reconnect_thread = None
        
        # Create MQTT client
        self.client = mqtt.Client(client_id=self.client_id)
        self._setup_callbacks()
        
        logger.info(f"SimpleMqttClient created: {self.client_id}")
    
    def _setup_callbacks(self):
        """Setup MQTT client callbacks."""
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_subscribe = self._on_subscribe
        self.client.on_publish = self._on_publish
        self.client.on_log = self._on_log
    
    def _on_connect(self, client, userdata, flags, rc):
        """Called when MQTT connection is established."""
        with self._lock:
            if rc == 0:
                self.connected = True
                self.connecting = False
                logger.info(f"MQTT connected to {self.broker}:{self.port}")
                
                # Re-subscribe to all topics
                self._resubscribe_all()
            else:
                self.connected = False
                self.connecting = False
                logger.error(f"MQTT connection failed with code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Called when MQTT connection is lost."""
        with self._lock:
            was_connected = self.connected
            self.connected = False
            self.connecting = False
            
            if was_connected:
                if rc == 0:
                    logger.info("MQTT disconnected gracefully")
                else:
                    logger.warning(f"MQTT disconnected unexpectedly (code {rc})")
                    
                    # Start automatic reconnection
                    if self._reconnect_enabled:
                        self._start_reconnect_thread()
    
    def _on_message(self, client, userdata, msg):
        """Called when MQTT message is received."""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            # Try to parse as JSON
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                # Use raw string if not JSON
                data = payload
            
            # Call message handler
            if self.message_callback:
                try:
                    self.message_callback(topic, data)
                except Exception as e:
                    logger.error(f"Message callback error: {e}")
            
            logger.debug(f"MQTT message received: {topic}")
            
        except Exception as e:
            logger.error(f"Message processing error: {e}")
    
    def _on_subscribe(self, client, userdata, mid, granted_qos):
        """Called when subscription is acknowledged."""
        logger.debug(f"MQTT subscription acknowledged: mid={mid}")
    
    def _on_publish(self, client, userdata, mid):
        """Called when message is published."""
        logger.debug(f"MQTT message published: mid={mid}")
    
    def _on_log(self, client, userdata, level, buf):
        """Called for MQTT client logging."""
        # Only log errors and warnings to avoid spam
        if level <= mqtt.MQTT_LOG_WARNING:
            logger.debug(f"MQTT log ({level}): {buf}")
    
    def _resubscribe_all(self):
        """Re-subscribe to all previously subscribed topics."""
        with self._lock:
            for topic in self._subscribed_topics.copy():
                try:
                    result = self.client.subscribe(topic)
                    if result[0] != mqtt.MQTT_ERR_SUCCESS:
                        logger.warning(f"Failed to re-subscribe to {topic}")
                except Exception as e:
                    logger.error(f"Re-subscription error for {topic}: {e}")
    
    def _start_reconnect_thread(self):
        """Start automatic reconnection thread."""
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            return
        
        self._reconnect_thread = threading.Thread(target=self._reconnect_loop, daemon=True)
        self._reconnect_thread.start()
        logger.info("Started MQTT reconnection thread")
    
    def _reconnect_loop(self):
        """Automatic reconnection loop."""
        while self._reconnect_enabled and not self.connected:
            try:
                logger.info(f"Attempting MQTT reconnection to {self.broker}...")
                
                with self._lock:
                    if self.connecting:
                        continue
                    
                    self.connecting = True
                
                # Attempt connection
                try:
                    self.client.reconnect()
                    self.client.loop_start()
                    
                    # Wait for connection or timeout
                    for _ in range(50):  # 5 second timeout
                        if self.connected:
                            logger.info("MQTT reconnection successful")
                            return
                        time.sleep(0.1)
                    
                    # Timeout - connection failed
                    with self._lock:
                        self.connecting = False
                    
                except Exception as e:
                    logger.debug(f"Reconnection attempt failed: {e}")
                    with self._lock:
                        self.connecting = False
                
                # Wait before next attempt
                if self._reconnect_enabled:
                    time.sleep(self._reconnect_delay)
                
            except Exception as e:
                logger.error(f"Reconnection loop error: {e}")
                time.sleep(self._reconnect_delay)
    
    # =================================================================
    # Public Interface
    # =================================================================
    
    def connect(self, timeout: float = 10.0) -> bool:
        """
        Connect to MQTT broker.
        
        Args:
            timeout: Connection timeout in seconds
            
        Returns:
            True if connected successfully
        """
        try:
            with self._lock:
                if self.connected:
                    return True
                
                if self.connecting:
                    # Wait for ongoing connection
                    start_time = time.time()
                    while self.connecting and (time.time() - start_time) < timeout:
                        time.sleep(0.1)
                    return self.connected
                
                self.connecting = True
            
            logger.info(f"Connecting to MQTT broker {self.broker}:{self.port}")
            
            # Set up connection parameters
            self.client.clean_session = True
            
            # Connect
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            
            # Wait for connection
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            with self._lock:
                self.connecting = False
            
            if self.connected:
                logger.info(f"MQTT connected successfully to {self.broker}")
            else:
                logger.error(f"MQTT connection timeout after {timeout}s")
            
            return self.connected
            
        except Exception as e:
            logger.error(f"MQTT connection error: {e}")
            with self._lock:
                self.connecting = False
                self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker."""
        try:
            with self._lock:
                self._reconnect_enabled = False
                
                if self._reconnect_thread and self._reconnect_thread.is_alive():
                    # Give reconnection thread time to stop
                    pass
            
            if self.connected:
                self.client.loop_stop()
                self.client.disconnect()
                logger.info("MQTT disconnected")
            
            with self._lock:
                self.connected = False
                self.connecting = False
                
        except Exception as e:
            logger.error(f"MQTT disconnect error: {e}")
    
    def subscribe(self, topic: str, callback: Optional[Callable] = None) -> bool:
        """
        Subscribe to MQTT topic.
        
        Args:
            topic: MQTT topic to subscribe to
            callback: Optional message callback (overrides global callback)
            
        Returns:
            True if subscription was successful
        """
        try:
            if not self.connected:
                logger.warning(f"Cannot subscribe to {topic} - not connected")
                return False
            
            # Set callback if provided
            if callback:
                self.message_callback = callback
            
            # Subscribe
            result = self.client.subscribe(topic)
            success = result[0] == mqtt.MQTT_ERR_SUCCESS
            
            if success:
                with self._lock:
                    self._subscribed_topics.add(topic)
                logger.debug(f"Subscribed to MQTT topic: {topic}")
            else:
                logger.warning(f"Failed to subscribe to {topic}: error {result[0]}")
            
            return success
            
        except Exception as e:
            logger.error(f"MQTT subscription error for {topic}: {e}")
            return False
    
    def unsubscribe(self, topic: str) -> bool:
        """
        Unsubscribe from MQTT topic.
        
        Args:
            topic: MQTT topic to unsubscribe from
            
        Returns:
            True if unsubscription was successful
        """
        try:
            if not self.connected:
                return False
            
            result = self.client.unsubscribe(topic)
            success = result[0] == mqtt.MQTT_ERR_SUCCESS
            
            if success:
                with self._lock:
                    self._subscribed_topics.discard(topic)
                logger.debug(f"Unsubscribed from MQTT topic: {topic}")
            
            return success
            
        except Exception as e:
            logger.error(f"MQTT unsubscription error for {topic}: {e}")
            return False
    
    def publish(self, topic: str, payload: Any, qos: int = 0, retain: bool = False) -> bool:
        """
        Publish message to MQTT topic.
        
        Args:
            topic: MQTT topic to publish to
            payload: Message payload (will be JSON-serialized if dict)
            qos: Quality of Service level (0, 1, or 2)
            retain: Whether message should be retained
            
        Returns:
            True if publish was successful
        """
        try:
            if not self.connected:
                logger.warning(f"Cannot publish to {topic} - not connected")
                return False
            
            # Serialize payload
            if isinstance(payload, dict):
                payload_str = json.dumps(payload)
            elif isinstance(payload, (list, tuple)):
                payload_str = json.dumps(payload)
            else:
                payload_str = str(payload)
            
            # Publish
            result = self.client.publish(topic, payload_str, qos, retain)
            success = result.rc == mqtt.MQTT_ERR_SUCCESS
            
            if success:
                logger.debug(f"Published to MQTT topic: {topic}")
            else:
                logger.warning(f"Failed to publish to {topic}: error {result.rc}")
            
            return success
            
        except Exception as e:
            logger.error(f"MQTT publish error for {topic}: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if MQTT client is connected."""
        return self.connected
    
    def get_status(self) -> Dict[str, Any]:
        """Get current client status."""
        with self._lock:
            return {
                'connected': self.connected,
                'connecting': self.connecting,
                'broker': self.broker,
                'port': self.port,
                'client_id': self.client_id,
                'subscribed_topics': list(self._subscribed_topics),
                'reconnect_enabled': self._reconnect_enabled
            }
    
    def set_message_callback(self, callback: Callable[[str, Any], None]):
        """
        Set global message callback.
        
        Args:
            callback: Function to call when message is received.
                     Signature: callback(topic: str, data: Any)
        """
        self.message_callback = callback
    
    def enable_reconnect(self, enabled: bool = True, delay: float = 5.0):
        """
        Enable or disable automatic reconnection.
        
        Args:
            enabled: Whether to enable automatic reconnection
            delay: Delay between reconnection attempts in seconds
        """
        with self._lock:
            self._reconnect_enabled = enabled
            self._reconnect_delay = delay
        
        logger.info(f"MQTT reconnection {'enabled' if enabled else 'disabled'}")
    
    def force_reconnect(self) -> bool:
        """
        Force immediate reconnection attempt.
        
        Returns:
            True if reconnection was successful
        """
        logger.info("Forcing MQTT reconnection...")
        
        # Disconnect first
        self.disconnect()
        time.sleep(0.5)
        
        # Reconnect
        self._reconnect_enabled = True
        return self.connect()
    
    # =================================================================
    # Context Manager Support
    # =================================================================
    
    def __enter__(self):
        """Context manager entry."""
        if not self.connect():
            raise RuntimeError("Failed to connect to MQTT broker")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
