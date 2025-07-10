"""
Main Presenter for EGEA Suspension Tester.

Responsibility: Coordinates between views and models, handles business logic.
Follows MVP pattern - View knows nothing about Model.
"""

import threading
import time
import logging
from typing import Dict, Any, Optional, Callable
from pathlib import Path
import sys

# Add project root to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

logger = logging.getLogger(__name__)


class MainPresenter:
    """
    Main presenter that orchestrates the entire application.
    
    Responsibilities:
    - Coordinate between view and models
    - Handle user interactions from view
    - Manage MQTT communication
    - Control test execution
    - Update UI based on model changes
    """
    
    def __init__(self):
        # Components (injected)
        self.view = None
        self.data_buffer = None
        self.mqtt_client = None
        self.config_manager = None
        
        # Application state
        self.is_running = False
        self.update_thread = None
        self._shutdown_event = threading.Event()
        
        # Update intervals
        self._ui_update_interval = 0.1  # 10 FPS
        self._last_ui_update = 0
        
        logger.info("MainPresenter initialized")
    
    def initialize(self, view, data_buffer, config_manager=None):
        """
        Initialize presenter with required components.
        
        Args:
            view: Main window view
            data_buffer: Data buffer model
            config_manager: Configuration manager (optional)
        """
        self.view = view
        self.data_buffer = data_buffer
        self.config_manager = config_manager
        
        # Set up view callbacks
        self._setup_view_callbacks()
        
        # Initialize MQTT
        self._initialize_mqtt()
        
        # Start update loop
        self.start()
        
        logger.info("MainPresenter initialized with components")
    
    def _setup_view_callbacks(self):
        """Sets up callbacks from view to presenter."""
        if not self.view:
            return
        
        callbacks = {
            'on_start_test': self.handle_start_test,
            'on_stop_test': self.handle_stop_test,
            'on_emergency_stop': self.handle_emergency_stop,
            'on_discovery_dialog': self.handle_discovery_dialog,
            'on_reconnect_mqtt': self.handle_reconnect_mqtt,
            'on_clear_buffer': self.handle_clear_buffer,
            'on_closing': self.handle_closing
        }
        
        self.view.set_callbacks(callbacks)
        logger.info("View callbacks configured")
    
    def _initialize_mqtt(self):
        """Initialize MQTT connection with auto-discovery."""
        try:
            self.view.log_message("🔍 MQTT", "Starting broker discovery...", "info")
            
            # Get best broker from config
            broker = self._get_best_broker()
            
            # Create and connect MQTT client
            self.mqtt_client = self._create_mqtt_client(broker)
            
            if self.mqtt_client and self.mqtt_client.connect():
                self.view.update_broker_status(broker, "Connected ✅", True)
                self.view.log_message("✅ MQTT", f"Connected to {broker}", "success")
                
                # Subscribe to standard topics
                self._subscribe_to_topics()
            else:
                self.view.update_broker_status(broker, "Connection failed ❌", False)
                self.view.log_message("❌ MQTT", f"Failed to connect to {broker}", "error")
        
        except Exception as e:
            logger.error(f"MQTT initialization failed: {e}")
            self.view.log_message("❌ MQTT", f"Initialization failed: {e}", "error")
    
    def _get_best_broker(self) -> str:
        """Get best available MQTT broker."""
        if self.config_manager:
            try:
                return self.config_manager.get_mqtt_broker()
            except Exception as e:
                logger.warning(f"Config manager broker discovery failed: {e}")
        
        # Fallback brokers
        fallback_brokers = [
            "192.168.0.249",
            "192.168.0.100", 
            "192.168.1.100",
            "localhost"
        ]
        
        for broker in fallback_brokers:
            if self._test_broker_connection(broker):
                return broker
        
        return "localhost"  # Last resort
    
    def _test_broker_connection(self, broker: str) -> bool:
        """Test if broker is reachable."""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            result = sock.connect_ex((broker, 1883))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def _create_mqtt_client(self, broker: str):
        """Create MQTT client with optimized settings."""
        try:
            # Import the SimpleMqttClient from the original file or create new one
            from ..processing.mqtt_client import SimpleMqttClient
            client = SimpleMqttClient(
                broker=broker,
                port=1883,
                client_id=f"egea_gui_{int(time.time())}"
            )
            return client
            
        except ImportError:
            # Fallback: Create inline MQTT client
            logger.warning("SimpleMqttClient not found, using fallback")
            return self._create_fallback_mqtt_client(broker)
    
    def _create_fallback_mqtt_client(self, broker: str):
        """Creates a fallback MQTT client if main one not available."""
        try:
            import paho.mqtt.client as mqtt
            
            class FallbackMqttClient:
                def __init__(self, broker: str):
                    self.broker = broker
                    self.client = mqtt.Client(client_id=f"egea_gui_{int(time.time())}")
                    self.connected = False
                    self.client.on_connect = self._on_connect
                    self.client.on_message = self._on_message
                
                def _on_connect(self, client, userdata, flags, rc):
                    self.connected = (rc == 0)
                
                def _on_message(self, client, userdata, msg):
                    if hasattr(self, 'message_callback'):
                        try:
                            import json
                            topic = msg.topic
                            payload = json.loads(msg.payload.decode('utf-8'))
                            self.message_callback(topic, payload)
                        except Exception as e:
                            logger.debug(f"Message processing error: {e}")
                
                def connect(self) -> bool:
                    try:
                        self.client.connect(self.broker, 1883, 60)
                        self.client.loop_start()
                        # Wait for connection
                        for _ in range(50):  # 5 second timeout
                            if self.connected:
                                return True
                            time.sleep(0.1)
                        return False
                    except Exception:
                        return False
                
                def subscribe(self, topic: str, callback=None):
                    if callback:
                        self.message_callback = callback
                    result = self.client.subscribe(topic)
                    return result[0] == mqtt.MQTT_ERR_SUCCESS
                
                def publish(self, topic: str, payload):
                    import json
                    if isinstance(payload, dict):
                        payload = json.dumps(payload)
                    result = self.client.publish(topic, payload)
                    return result.rc == mqtt.MQTT_ERR_SUCCESS
                
                def disconnect(self):
                    try:
                        self.client.loop_stop()
                        self.client.disconnect()
                    except Exception:
                        pass
                
                def is_connected(self):
                    return self.connected
            
            return FallbackMqttClient(broker)
            
        except Exception as e:
            logger.error(f"Failed to create fallback MQTT client: {e}")
            return None
    
    def _subscribe_to_topics(self):
        """Subscribe to standard MQTT topics."""
        if not self.mqtt_client:
            return
        
        topics = [
            "suspension/measurements/processed",
            "suspension/test/result", 
            "suspension/status",
            "suspension/commands"
        ]
        
        success_count = 0
        for topic in topics:
            if self.mqtt_client.subscribe(topic, self._handle_mqtt_message):
                success_count += 1
                self.view.log_message("📡 MQTT", f"Subscribed: {topic}")
        
        self.view.log_message("📡 MQTT", f"{success_count}/{len(topics)} topics subscribed",
                             "success" if success_count > 0 else "warning")
    
    def _handle_mqtt_message(self, topic: str, data: Any):
        """Handle incoming MQTT messages."""
        try:
            logger.debug(f"MQTT message: {topic}")
            
            if topic == "suspension/measurements/processed":
                self._process_measurement_data(data)
            elif topic == "suspension/test/result":
                self._process_test_result(data)
            elif topic == "suspension/status":
                self._process_status_update(data)
            else:
                self.view.log_message("📨 MQTT", f"Unknown topic: {topic}")
        
        except Exception as e:
            logger.error(f"MQTT message handling error: {e}")
            self.view.log_message("❌ MQTT", f"Message processing failed: {e}", "error")
    
    def _process_measurement_data(self, data: Dict[str, Any]):
        """Process measurement data from MQTT."""
        try:
            # Add to data buffer
            if self.data_buffer:
                self.data_buffer.add_data(data)
            
            # Rate-limited UI updates will happen in update loop
            
        except Exception as e:
            logger.error(f"Measurement data processing error: {e}")
    
    def _process_test_result(self, data: Dict[str, Any]):
        """Process test result data."""
        try:
            if 'egea_result' in data:
                result = data['egea_result']
                passing = result.get('passing', False)
                phase_shift = result.get('min_phase_shift', 0)
                
                result_text = "PASSED ✅" if passing else "FAILED ❌"
                self.view.log_message("🏁 Test", f"EGEA Result: {result_text} (φ={phase_shift:.1f}°)",
                                     "success" if passing else "warning")
        except Exception as e:
            logger.error(f"Test result processing error: {e}")
    
    def _process_status_update(self, data: Dict[str, Any]):
        """Process status update data."""
        try:
            source = data.get('source', 'System')
            message = data.get('message', data.get('status', 'Update'))
            self.view.log_message(f"📡 {source}", message)
        except Exception as e:
            logger.error(f"Status update processing error: {e}")
    
    # =================================================================
    # User Interaction Handlers
    # =================================================================
    
    def handle_start_test(self, test_config: Dict[str, Any]):
        """Handle start test request from view."""
        try:
            position = test_config.get('position', 'front_left')
            vehicle_type = test_config.get('vehicle_type', 'M1')
            duration = test_config.get('duration', 30.0)
            
            # Start test in data buffer
            if self.data_buffer:
                self.data_buffer.start_test(position, vehicle_type, duration)
            
            # Send MQTT command
            if self.mqtt_client and self.mqtt_client.is_connected():
                command = {
                    "command": "start_test",
                    "position": position,
                    "vehicle_type": vehicle_type,
                    "test_method": "egea_phase_shift",
                    "duration": duration,
                    "timestamp": time.time(),
                    "source": "egea_gui"
                }
                self.mqtt_client.publish("suspension/commands", command)
            
            # Update view
            self.view.enable_test_controls(False)
            self.view.log_message("🚀 Test", f"EGEA test started: {position} ({vehicle_type})", "success")
            
        except Exception as e:
            logger.error(f"Start test error: {e}")
            self.view.log_message("❌ Test", f"Start test failed: {e}", "error")
    
    def handle_stop_test(self):
        """Handle stop test request from view."""
        try:
            # Stop test in data buffer
            if self.data_buffer:
                self.data_buffer.stop_test()
            
            # Send MQTT stop command
            if self.mqtt_client and self.mqtt_client.is_connected():
                command = {
                    "command": "stop_test",
                    "timestamp": time.time(),
                    "source": "egea_gui"
                }
                self.mqtt_client.publish("suspension/commands", command)
            
            # Update view
            self.view.enable_test_controls(True)
            self.view.log_message("⏹ Test", "EGEA test stopped", "info")
            
        except Exception as e:
            logger.error(f"Stop test error: {e}")
            self.view.log_message("❌ Test", f"Stop test failed: {e}", "error")
    
    def handle_emergency_stop(self):
        """Handle emergency stop request from view."""
        try:
            # Stop test immediately
            if self.data_buffer and self.data_buffer.is_test_active():
                self.handle_stop_test()
            
            # Send emergency command
            if self.mqtt_client and self.mqtt_client.is_connected():
                emergency_cmd = {
                    "command": "emergency_stop",
                    "timestamp": time.time(),
                    "source": "egea_gui",
                    "reason": "user_initiated"
                }
                self.mqtt_client.publish("suspension/commands", emergency_cmd)
            
            self.view.log_message("🚨 EMERGENCY", "Emergency stop triggered!", "error")
            
            # Show confirmation dialog
            self.view.show_message_box("Emergency Stop", 
                                     "Emergency stop has been triggered!\nAll tests have been stopped.",
                                     "warning")
            
        except Exception as e:
            logger.error(f"Emergency stop error: {e}")
            self.view.log_message("❌ EMERGENCY", f"Emergency stop failed: {e}", "error")
    
    def handle_discovery_dialog(self):
        """Handle discovery dialog request from view."""
        try:
            # Try to open intelligent discovery dialog
            try:
                from smart_suspension_discovery import EnhancedSuspensionDiscoveryDialog
                
                dialog = EnhancedSuspensionDiscoveryDialog(self.view.root)
                result = dialog.show()
                
                if result:
                    ip = result['ip']
                    confidence = result.get('confidence', 0) * 100
                    
                    # Update config and reconnect
                    if self.config_manager:
                        self.config_manager.add_fallback_broker(ip)
                    
                    self.view.log_message("🎯 Discovery", 
                                         f"Broker selected: {ip} (Confidence: {confidence:.0f}%)", 
                                         "success")
                    
                    # Reconnect with new broker
                    self._reconnect_to_broker(ip)
                    
            except ImportError:
                # Fallback to simple dialog
                self.view.log_message("⚠️ Discovery", "Advanced discovery not available, using fallback", "warning")
                self._show_simple_discovery_dialog()
                
        except Exception as e:
            logger.error(f"Discovery dialog error: {e}")
            self.view.log_message("❌ Discovery", f"Discovery failed: {e}", "error")
    
    def _show_simple_discovery_dialog(self):
        """Show simple IP input dialog as fallback."""
        try:
            import tkinter.simpledialog as simpledialog
            
            ip = simpledialog.askstring("MQTT Broker", 
                                      "Enter MQTT broker IP address:",
                                      initialvalue="192.168.0.249")
            
            if ip and self._test_broker_connection(ip):
                if self.config_manager:
                    self.config_manager.add_fallback_broker(ip)
                self._reconnect_to_broker(ip)
                self.view.log_message("🔍 Discovery", f"Manual broker configured: {ip}", "success")
            elif ip:
                self.view.show_message_box("Connection Failed", 
                                         f"Could not connect to {ip}:1883\n"
                                         "Please check IP address and broker status.",
                                         "error")
                
        except Exception as e:
            logger.error(f"Simple discovery dialog error: {e}")
    
    def handle_reconnect_mqtt(self):
        """Handle MQTT reconnection request from view."""
        try:
            self.view.log_message("🔄 MQTT", "Reconnecting...", "info")
            
            # Disconnect current client
            if self.mqtt_client:
                self.mqtt_client.disconnect()
            
            # Reinitialize MQTT
            self._initialize_mqtt()
            
        except Exception as e:
            logger.error(f"MQTT reconnection error: {e}")
            self.view.log_message("❌ MQTT", f"Reconnection failed: {e}", "error")
    
    def _reconnect_to_broker(self, broker_ip: str):
        """Reconnect to specific broker."""
        try:
            # Disconnect current
            if self.mqtt_client:
                self.mqtt_client.disconnect()
            
            # Create new client
            self.mqtt_client = self._create_mqtt_client(broker_ip)
            
            if self.mqtt_client and self.mqtt_client.connect():
                self.view.update_broker_status(broker_ip, "Connected ✅", True)
                self.view.log_message("✅ MQTT", f"Reconnected to {broker_ip}", "success")
                self._subscribe_to_topics()
            else:
                self.view.update_broker_status(broker_ip, "Connection failed ❌", False)
                self.view.log_message("❌ MQTT", f"Failed to reconnect to {broker_ip}", "error")
                
        except Exception as e:
            logger.error(f"Broker reconnection error: {e}")
    
    def handle_clear_buffer(self):
        """Handle clear buffer request from view."""
        try:
            if self.data_buffer:
                self.data_buffer.clear()
                self.view.log_message("🗑 System", "Data buffer cleared", "info")
                
                # Clear charts in view
                if hasattr(self.view, 'chart_widget') and self.view.chart_widget:
                    self.view.chart_widget.clear_charts()
            
        except Exception as e:
            logger.error(f"Clear buffer error: {e}")
            self.view.log_message("❌ System", f"Clear buffer failed: {e}", "error")
    
    def handle_closing(self):
        """Handle application closing request from view."""
        try:
            # Ask for confirmation if test is running
            if self.data_buffer and self.data_buffer.is_test_active():
                result = self.view.show_message_box("Test Running", 
                                                   "A test is currently running.\n"
                                                   "Stop test and exit?",
                                                   "question")
                if result != 'yes':
                    return
                
                # Stop the test
                self.handle_stop_test()
            
            # Shutdown presenter
            self.shutdown()
            
            # Close view
            self.view.root.destroy()
            
        except Exception as e:
            logger.error(f"Closing error: {e}")
            # Force close anyway
            self.view.root.destroy()
    
    # =================================================================
    # Application Lifecycle
    # =================================================================
    
    def start(self):
        """Start the presenter and update loop."""
        self.is_running = True
        
        # Start update thread
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
        
        logger.info("MainPresenter started")
    
    def shutdown(self):
        """Shutdown presenter and cleanup resources."""
        try:
            self.is_running = False
            self._shutdown_event.set()
            
            # Stop test if running
            if self.data_buffer and self.data_buffer.is_test_active():
                self.data_buffer.stop_test()
            
            # Disconnect MQTT
            if self.mqtt_client:
                try:
                    self.mqtt_client.disconnect()
                    self.view.log_message("🔌 System", "MQTT disconnected", "info")
                except Exception as e:
                    logger.error(f"MQTT disconnect error: {e}")
            
            # Wait for update thread
            if self.update_thread and self.update_thread.is_alive():
                self.update_thread.join(timeout=1.0)
            
            logger.info("MainPresenter shutdown complete")
            
        except Exception as e:
            logger.error(f"Shutdown error: {e}")
    
    def _update_loop(self):
        """Main update loop running in background thread."""
        while self.is_running and not self._shutdown_event.is_set():
            try:
                current_time = time.time()
                
                # Rate-limited UI updates
                if current_time - self._last_ui_update >= self._ui_update_interval:
                    self._update_ui()
                    self._last_ui_update = current_time
                
                # Sleep to prevent high CPU usage
                time.sleep(0.05)  # 20 FPS check rate
                
            except Exception as e:
                logger.error(f"Update loop error: {e}")
                time.sleep(0.5)  # Longer sleep on error
    
    def _update_ui(self):
        """Update UI components with current data."""
        try:
            if not self.data_buffer or not self.view:
                return
            
            # Update data count
            data_count = self.data_buffer.get_data_count()
            self.view.update_data_count(data_count)
            
            # Update EGEA status
            egea_status = self.data_buffer.get_egea_status()
            self.view.update_egea_status(egea_status)
            
            # Update charts with recent data
            if hasattr(self.view, 'chart_widget') and self.view.chart_widget:
                recent_data = self.data_buffer.get_recent_data(500)
                if recent_data:
                    # Use threading to prevent UI blocking
                    def update_charts():
                        try:
                            self.view.chart_widget.update_charts(recent_data)
                        except Exception as e:
                            logger.debug(f"Chart update error: {e}")
                    
                    # Schedule chart update in main thread
                    self.view.root.after_idle(update_charts)
            
        except Exception as e:
            logger.debug(f"UI update error: {e}")
    
    # =================================================================
    # Utility Methods
    # =================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """Get current presenter status."""
        return {
            'running': self.is_running,
            'mqtt_connected': self.mqtt_client.is_connected() if self.mqtt_client else False,
            'test_active': self.data_buffer.is_test_active() if self.data_buffer else False,
            'data_count': self.data_buffer.get_data_count() if self.data_buffer else 0
        }
    
    def send_test_command(self, command: Dict[str, Any]):
        """Send custom test command via MQTT."""
        try:
            if self.mqtt_client and self.mqtt_client.is_connected():
                command['timestamp'] = time.time()
                command['source'] = 'egea_gui'
                success = self.mqtt_client.publish("suspension/commands", command)
                
                if success:
                    self.view.log_message("📡 Command", f"Sent: {command.get('command', 'unknown')}", "success")
                else:
                    self.view.log_message("❌ Command", "Failed to send command", "error")
                    
                return success
            else:
                self.view.log_message("❌ Command", "MQTT not connected", "error")
                return False
                
        except Exception as e:
            logger.error(f"Send command error: {e}")
            self.view.log_message("❌ Command", f"Send failed: {e}", "error")
            return False
