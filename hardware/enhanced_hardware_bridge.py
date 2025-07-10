#!/usr/bin/env python3
"""
Enhanced Hardware Bridge für Fahrwerkstester
Unterstützt Hardware, Simulator und Hybrid-Modi

Neue Funktionen:
- Simulator-Modus: Kann mit Simulator über CAN kommunizieren
- Datensammlung: Sammelt komplette Tests vor Processing
- Dual-Mode: Hardware und Simulator gleichzeitig
"""

import asyncio
import json
import logging
import signal
import sys
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

# Füge Common Library zum Path hinzu
sys.path.append(str(Path(__file__).parent.parent / "common"))

# Import from the common library
try:
    from common.suspension_core.can.can_interface import CanInterface
    from common.suspension_core.can.interface_factory import create_can_interface
    from common.suspension_core.can.converters.json_converter import CanMessageConverter
    from common.suspension_core.config.manager import ConfigManager
    from common.suspension_core.mqtt.handler import MqttHandler
    from common.suspension_core.protocols import create_protocol
    from common.suspension_core.protocols.messages import (
        Position,
        TestState,
        create_command_message,
        create_measurement_message,
        create_raw_data_message,
        create_status_message,
    )
    SUSPENSION_CORE_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Suspension Core nicht verfügbar: {e}")
    SUSPENSION_CORE_AVAILABLE = False

logger = logging.getLogger(__name__)


class BridgeMode(Enum):
    """Modi für Enhanced Hardware Bridge"""
    HARDWARE = "hardware"      # Nur echte Hardware
    SIMULATOR = "simulator"    # Nur Simulator
    HYBRID = "hybrid"         # Beide gleichzeitig


@dataclass
class TestSession:
    """Container für eine Test-Session"""
    session_id: str
    position: str              # front_left, front_right, etc.
    start_time: float
    end_time: Optional[float] = None
    raw_data: List[Dict[str, Any]] = None
    metadata: Dict[str, Any] = None
    status: str = "running"    # running, completed, failed
    
    def __post_init__(self):
        if self.raw_data is None:
            self.raw_data = []
        if self.metadata is None:
            self.metadata = {}


class SimplifiedMqttClient:
    """
    Vereinfachter MQTT-Client als Fallback falls suspension_core nicht verfügbar
    """
    
    def __init__(self, broker: str, port: int, client_id: str):
        self.broker = broker
        self.port = port
        self.client_id = client_id
        self.connected = False
        self.callbacks = {}
        
        try:
            import paho.mqtt.client as mqtt
            self.client = mqtt.Client(client_id=client_id)
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
        except ImportError:
            self.client = None
            logger.error("paho-mqtt nicht verfügbar")
    
    async def connect_async(self):
        if self.client:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            
            # Warte auf Verbindung
            for _ in range(50):
                if self.connected:
                    return True
                await asyncio.sleep(0.1)
        return False
    
    async def disconnect_async(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
    
    async def subscribe_async(self, topic: str, callback):
        if self.client and self.connected:
            self.client.subscribe(topic)
            self.callbacks[topic] = callback
    
    async def publish_async(self, topic: str, payload: Dict[str, Any]):
        if self.client and self.connected:
            message = json.dumps(payload)
            self.client.publish(topic, message)
    
    def _on_connect(self, client, userdata, flags, rc):
        self.connected = (rc == 0)
        logger.info(f"MQTT verbunden: {self.connected}")
    
    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        logger.info("MQTT getrennt")
    
    def _on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            for subscribed_topic, callback in self.callbacks.items():
                if topic.startswith(subscribed_topic.rstrip('#')):
                    asyncio.create_task(callback(topic, payload))
                    break
        except Exception as e:
            logger.error(f"MQTT-Message-Fehler: {e}")


class EnhancedHardwareBridge:
    """
    Enhanced Hardware Bridge mit Simulator-Unterstützung
    
    Funktionen:
    - Multi-Mode-Betrieb (Hardware/Simulator/Hybrid)
    - Vollständige Datensammlung vor Processing
    - Intelligente CAN-Message-Routing
    - Robuste Fehlerbehandlung
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialisiert die Enhanced Hardware Bridge
        
        Args:
            config_path: Pfad zur Konfigurationsdatei
        """
        # Konfiguration laden
        if SUSPENSION_CORE_AVAILABLE:
            self.config = ConfigManager(config_path)
        else:
            # Fallback-Konfiguration
            self.config = self._load_fallback_config(config_path)
        
        # Bridge-Modus bestimmen
        mode_str = self.config.get(["hardware_bridge", "mode"], "simulator")
        try:
            self.bridge_mode = BridgeMode(mode_str)
        except ValueError:
            logger.warning(f"Unbekannter Bridge-Modus: {mode_str}, verwende Simulator")
            self.bridge_mode = BridgeMode.SIMULATOR
        
        # Hardware-Komponenten
        self.can_interface = None
        self.simulator_can_interface = None
        self.protocol = None
        self.can_converter = None
        
        # MQTT-Handler
        if SUSPENSION_CORE_AVAILABLE:
            self.mqtt_handler = MqttHandler(
                broker=self.config.get(["mqtt", "broker"], "localhost"),
                port=self.config.get(["mqtt", "port"], 1883),
                client_id=f"enhanced_hardware_bridge_{int(time.time())}",
                app_type="bridge"
            )
        else:
            self.mqtt_handler = SimplifiedMqttClient(
                broker=self.config.get(["mqtt", "broker"], "localhost"),
                port=self.config.get(["mqtt", "port"], 1883),
                client_id=f"enhanced_hardware_bridge_{int(time.time())}"
            )
        
        # Test-Session-Management
        self.current_session: Optional[TestSession] = None
        self.session_history: List[TestSession] = []
        self.max_history_size = self.config.get(["bridge", "max_history"], 10)
        
        # Datensammlung-Parameter
        self.data_buffer_size = self.config.get(["bridge", "buffer_size"], 10000)
        self.auto_save_interval = self.config.get(["bridge", "auto_save_interval"], 30.0)
        
        # Service-Status
        self.running = False
        self.message_count = 0
        self.last_message_time = None
        
        # Threading für asynchrone Verarbeitung
        self.message_queue = deque(maxlen=self.data_buffer_size)
        self.queue_lock = threading.Lock()
        
        # Graceful Shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"Enhanced Hardware Bridge initialisiert - Modus: {self.bridge_mode.value}")
    
    def _load_fallback_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Lädt Fallback-Konfiguration wenn ConfigManager nicht verfügbar"""
        default_config = {
            "hardware_bridge": {
                "mode": "simulator"
            },
            "mqtt": {
                "broker": "localhost",
                "port": 1883
            },
            "bridge": {
                "max_history": 10,
                "buffer_size": 10000,
                "auto_save_interval": 30.0
            },
            "can": {
                "interface": "vcan0",
                "baudrate": 1000000,
                "protocol": "eusama"
            }
        }
        
        if config_path and Path(config_path).exists():
            try:
                import yaml
                with open(config_path, 'r') as f:
                    file_config = yaml.safe_load(f)
                    # Merge configurations
                    default_config.update(file_config)
            except Exception as e:
                logger.warning(f"Konfigurationsdatei konnte nicht geladen werden: {e}")
        
        return type('Config', (), {
            'get': lambda self, path, default=None: self._get_nested(default_config, path, default),
            '_get_nested': lambda self, d, path, default: 
                d.get(path[0], default) if len(path) == 1 
                else self._get_nested(d.get(path[0], {}), path[1:], default) if path[0] in d 
                else default
        })()
    
    def _signal_handler(self, signum, frame):
        """Behandelt Shutdown-Signale"""
        logger.info(f"Signal {signum} empfangen, beende Service graceful...")
        self.running = False
    
    async def start(self):
        """Startet die Enhanced Hardware Bridge"""
        logger.info("Starte Enhanced Hardware Bridge...")
        
        try:
            # CAN-Interfaces initialisieren basierend auf Modus
            if not await self._init_can_interfaces():
                logger.error("CAN-Interface-Initialisierung fehlgeschlagen")
                return False
            
            # MQTT verbinden
            if not await self._connect_mqtt():
                logger.error("MQTT-Verbindung fehlgeschlagen")
                return False
            
            # Protokoll initialisieren
            self._init_protocol()
            
            self.running = True
            
            # Status senden
            await self._send_status("online", f"ready - mode: {self.bridge_mode.value}")
            
            # Haupt-Service-Loops starten
            await asyncio.gather(
                self._can_message_loop(),
                self._mqtt_message_loop(),
                self._data_processing_loop(),
                self._heartbeat_loop()
            )
            
            logger.info("Enhanced Hardware Bridge gestartet")
            return True
            
        except Exception as e:
            logger.error(f"Fehler beim Starten der Enhanced Hardware Bridge: {e}")
            return False
    
    async def stop(self):
        """Stoppt die Enhanced Hardware Bridge"""
        logger.info("Stoppe Enhanced Hardware Bridge...")
        self.running = False
        
        # Aktuelle Session beenden
        if self.current_session and self.current_session.status == "running":
            await self._complete_test_session("stopped")
        
        # Status senden
        await self._send_status("offline", "stopping")
        
        # Verbindungen trennen
        if self.can_interface:
            try:
                self.can_interface.disconnect()
            except:
                pass
        
        if self.simulator_can_interface:
            try:
                self.simulator_can_interface.disconnect()
            except:
                pass
        
        if self.mqtt_handler:
            await self.mqtt_handler.disconnect_async()
        
        logger.info("Enhanced Hardware Bridge gestoppt")
    
    async def _init_can_interfaces(self) -> bool:
        """
        Initialisiert CAN-Interfaces basierend auf Bridge-Modus
        
        Returns:
            True wenn erfolgreich
        """
        try:
            # Für Simulator-Modus: Simuliere CAN-Interface
            if self.bridge_mode in [BridgeMode.SIMULATOR, BridgeMode.HYBRID]:
                logger.info("Simulator-Modus: Erstelle virtuelles CAN-Interface...")
                self.simulator_can_interface = type('MockCanInterface', (), {
                    'send_message': lambda *args, **kwargs: None,
                    'recv_message': lambda *args, **kwargs: None,
                    'set_message_callback': lambda cb: None,
                    'disconnect': lambda: None
                })()
                logger.info("Virtuelles CAN-Interface für Simulator erstellt")
            
            # Für Hardware-Modus: Echtes CAN-Interface (falls verfügbar)
            if self.bridge_mode in [BridgeMode.HARDWARE, BridgeMode.HYBRID]:
                if SUSPENSION_CORE_AVAILABLE:
                    try:
                        self.can_interface = create_can_interface(
                            config=self.config,
                            simulation_type=None  # Echte Hardware
                        )
                        if self.can_interface:
                            self.can_interface.set_message_callback(self._handle_hardware_can_message)
                            logger.info("Hardware CAN-Interface erfolgreich initialisiert")
                        else:
                            logger.warning("Hardware CAN-Interface nicht verfügbar")
                    except Exception as e:
                        logger.warning(f"Hardware CAN-Interface Fehler: {e}")
                else:
                    logger.info("Suspension Core nicht verfügbar - Hardware-Modus nicht möglich")
            
            return True
            
        except Exception as e:
            logger.error(f"Fehler bei CAN-Interface-Initialisierung: {e}")
            return False
    
    async def _connect_mqtt(self) -> bool:
        """
        Stellt MQTT-Verbindung her und richtet Subscriptions ein
        
        Returns:
            True wenn erfolgreich
        """
        try:
            if hasattr(self.mqtt_handler, 'connect_async'):
                await self.mqtt_handler.connect_async()
            else:
                # Fallback für SimplifiedMqttClient
                await self.mqtt_handler.connect_async()
            
            # Command-Topics abonnieren
            await self.mqtt_handler.subscribe_async(
                "suspension/bridge/command",
                self._handle_bridge_command
            )
            
            # Test-Control-Topics abonnieren
            await self.mqtt_handler.subscribe_async(
                "suspension/test/start",
                self._handle_test_start_command
            )
            
            await self.mqtt_handler.subscribe_async(
                "suspension/test/stop",
                self._handle_test_stop_command
            )
            
            logger.info("MQTT-Verbindung und Subscriptions erfolgreich eingerichtet")
            return True
            
        except Exception as e:
            logger.error(f"MQTT-Verbindungsfehler: {e}")
            return False
    
    def _init_protocol(self):
        """Initialisiert das Protokoll"""
        if SUSPENSION_CORE_AVAILABLE:
            try:
                protocol_name = self.config.get(["can", "protocol"], "eusama")
                self.protocol = create_protocol(protocol_name)
                if SUSPENSION_CORE_AVAILABLE:
                    self.can_converter = CanMessageConverter()
                logger.info(f"Protokoll initialisiert: {protocol_name}")
            except Exception as e:
                logger.warning(f"Protokoll-Initialisierung fehlgeschlagen: {e}")
        else:
            logger.info("Mock-Protokoll für Fallback-Modus")
            self.protocol = type('MockProtocol', (), {
                'decode_message': lambda self, msg_id, data: {
                    'timestamp': time.time(),
                    'platform_position': 0.0,
                    'tire_force': 500.0,
                    'source': 'mock'
                }
            })()
    
    def _handle_hardware_can_message(self, message):
        """
        Behandelt CAN-Nachrichten von echter Hardware
        
        Args:
            message: CAN-Message
        """
        try:
            # Message in Queue einreihen mit Quelle
            message_data = {
                "source": "hardware",
                "timestamp": time.time(),
                "arbitration_id": getattr(message, 'arbitration_id', 0),
                "data": list(getattr(message, 'data', [])),
                "is_extended_id": getattr(message, 'is_extended_id', True)
            }
            
            with self.queue_lock:
                self.message_queue.append(message_data)
            
            self.message_count += 1
            self.last_message_time = time.time()
            
            logger.debug(f"Hardware CAN-Message empfangen: ID=0x{message_data['arbitration_id']:X}")
            
        except Exception as e:
            logger.error(f"Fehler bei Hardware CAN-Message-Verarbeitung: {e}")
    
    def _handle_simulator_can_message(self, message):
        """
        Behandelt CAN-Nachrichten vom Simulator
        
        Args:
            message: CAN-Message
        """
        try:
            # Message in Queue einreihen mit Quelle
            message_data = {
                "source": "simulator",
                "timestamp": time.time(),
                "arbitration_id": getattr(message, 'arbitration_id', 0),
                "data": list(getattr(message, 'data', [])),
                "is_extended_id": getattr(message, 'is_extended_id', True)
            }
            
            with self.queue_lock:
                self.message_queue.append(message_data)
            
            self.message_count += 1
            self.last_message_time = time.time()
            
            logger.debug(f"Simulator CAN-Message empfangen: ID=0x{message_data['arbitration_id']:X}")
            
        except Exception as e:
            logger.error(f"Fehler bei Simulator CAN-Message-Verarbeitung: {e}")
    
    async def _handle_bridge_command(self, topic: str, payload: Dict[str, Any]):
        """
        Behandelt Bridge-Commands über MQTT
        
        Args:
            topic: MQTT-Topic
            payload: Command-Payload
        """
        try:
            command = payload.get("command")
            
            if command == "status":
                await self._send_detailed_status()
            elif command == "set_mode":
                await self._set_bridge_mode(payload.get("mode"))
            elif command == "clear_buffer":
                await self._clear_message_buffer()
            elif command == "save_session":
                await self._save_current_session()
            else:
                logger.warning(f"Unbekanntes Bridge-Command: {command}")
                
        except Exception as e:
            logger.error(f"Fehler bei Bridge-Command-Verarbeitung: {e}")
    
    async def _handle_test_start_command(self, topic: str, payload: Dict[str, Any]):
        """
        Behandelt Test-Start-Commands
        
        Args:
            topic: MQTT-Topic
            payload: Test-Start-Payload
        """
        try:
            position = payload.get("position", "unknown")
            test_id = payload.get("test_id", str(uuid.uuid4()))
            
            # Neue Test-Session starten
            await self._start_test_session(position, test_id, payload)
            
            logger.info(f"Test-Session gestartet: {test_id} für Position: {position}")
            
        except Exception as e:
            logger.error(f"Fehler bei Test-Start: {e}")
    
    async def _handle_test_stop_command(self, topic: str, payload: Dict[str, Any]):
        """
        Behandelt Test-Stop-Commands
        
        Args:
            topic: MQTT-Topic
            payload: Test-Stop-Payload
        """
        try:
            # Aktuelle Session beenden
            if self.current_session:
                await self._complete_test_session("completed")
                logger.info(f"Test-Session beendet: {self.current_session.session_id}")
            else:
                logger.warning("Kein aktiver Test zum Beenden")
                
        except Exception as e:
            logger.error(f"Fehler bei Test-Stop: {e}")
    
    async def _start_test_session(self, position: str, test_id: str, metadata: Dict[str, Any]):
        """
        Startet eine neue Test-Session
        
        Args:
            position: Test-Position
            test_id: Eindeutige Test-ID
            metadata: Test-Metadaten
        """
        # Beende laufende Session falls vorhanden
        if self.current_session and self.current_session.status == "running":
            await self._complete_test_session("interrupted")
        
        # Neue Session erstellen
        self.current_session = TestSession(
            session_id=test_id,
            position=position,
            start_time=time.time(),
            metadata=metadata
        )
        
        # Session-Start über MQTT publizieren
        await self.mqtt_handler.publish_async(
            "suspension/test/session_started",
            {
                "session_id": test_id,
                "position": position,
                "timestamp": self.current_session.start_time,
                "bridge_mode": self.bridge_mode.value,
                "metadata": metadata
            }
        )
        
        logger.info(f"Test-Session gestartet: {test_id}")
    
    async def _complete_test_session(self, status: str = "completed"):
        """
        Beendet die aktuelle Test-Session
        
        Args:
            status: Session-Status (completed, failed, interrupted)
        """
        if not self.current_session:
            return
        
        # Session beenden
        self.current_session.end_time = time.time()
        self.current_session.status = status
        
        # Sammle alle Daten der Session
        session_data = []
        with self.queue_lock:
            # Filtere Daten für diese Session
            session_start = self.current_session.start_time
            session_data = [
                msg for msg in self.message_queue 
                if msg["timestamp"] >= session_start
            ]
        
        # Konvertiere CAN-Messages zu strukturierten Daten
        processed_data = []
        for msg in session_data:
            try:
                # Protokoll-spezifische Dekodierung
                decoded = self._decode_can_message(msg)
                if decoded:
                    processed_data.append(decoded)
            except Exception as e:
                logger.warning(f"Fehler bei Message-Dekodierung: {e}")
        
        # Setze verarbeitete Daten
        self.current_session.raw_data = processed_data
        
        # Publiziere komplettes Dataset
        await self._publish_complete_dataset()
        
        # Session zur Historie hinzufügen
        self.session_history.append(self.current_session)
        
        # Historie begrenzen
        if len(self.session_history) > self.max_history_size:
            self.session_history.pop(0)
        
        # Session abschließen
        session_id = self.current_session.session_id
        self.current_session = None
        
        logger.info(f"Test-Session abgeschlossen: {session_id} mit Status: {status}")
    
    def _decode_can_message(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Dekodiert CAN-Message basierend auf Protokoll
        
        Args:
            message_data: Rohe CAN-Message-Daten
            
        Returns:
            Dekodierte Daten oder None
        """
        try:
            if not self.protocol:
                return None
            
            # Protokoll-spezifische Dekodierung
            decoded = self.protocol.decode_message(
                message_data["arbitration_id"],
                message_data["data"]
            )
            
            if decoded:
                # Erweitere um Metadaten
                decoded.update({
                    "source": message_data["source"],
                    "timestamp": message_data["timestamp"],
                    "raw_id": message_data["arbitration_id"]
                })
                
                return decoded
            
        except Exception as e:
            logger.debug(f"Dekodierungsfehler für Message ID 0x{message_data['arbitration_id']:X}: {e}")
        
        return None
    
    async def _publish_complete_dataset(self):
        """Publiziert das komplette Dataset der aktuellen Session"""
        if not self.current_session:
            return
        
        # Erstelle komplettes Dataset
        complete_dataset = {
            "test_id": self.current_session.session_id,
            "position": self.current_session.position,
            "bridge_mode": self.bridge_mode.value,
            "start_time": self.current_session.start_time,
            "end_time": self.current_session.end_time,
            "duration": self.current_session.end_time - self.current_session.start_time,
            "raw_data": self.current_session.raw_data,
            "metadata": self.current_session.metadata,
            "statistics": {
                "total_messages": len(self.current_session.raw_data),
                "message_rate": len(self.current_session.raw_data) / (self.current_session.end_time - self.current_session.start_time),
                "data_sources": list(set(msg.get("source", "unknown") for msg in self.current_session.raw_data))
            }
        }
        
        # Publiziere für Pi Processing Service
        await self.mqtt_handler.publish_async(
            "suspension/raw_data/complete",
            complete_dataset
        )
        
        # Publiziere Test-Completion-Signal
        await self.mqtt_handler.publish_async(
            "suspension/test/completed",
            {
                "test_id": self.current_session.session_id,
                "position": self.current_session.position,
                "timestamp": self.current_session.end_time,
                "status": self.current_session.status,
                "data_points": len(self.current_session.raw_data)
            }
        )
        
        logger.info(f"Komplettes Dataset publiziert: {len(self.current_session.raw_data)} Datenpunkte")
    
    async def _can_message_loop(self):
        """CAN-Message-Loop für kontinuierliche Verarbeitung"""
        logger.info("CAN-Message-Loop gestartet")
        
        while self.running:
            try:
                # Kurze Pause um CPU zu entlasten
                await asyncio.sleep(0.01)
                
                # Simuliere CAN-Messages im Simulator-Modus
                if self.bridge_mode in [BridgeMode.SIMULATOR, BridgeMode.HYBRID]:
                    await self._simulate_can_messages()
                
            except Exception as e:
                logger.error(f"Fehler in CAN-Message-Loop: {e}")
                await asyncio.sleep(1.0)
        
        logger.info("CAN-Message-Loop beendet")
    
    async def _simulate_can_messages(self):
        """Simuliert CAN-Messages für Testing"""
        if self.current_session and self.current_session.status == "running":
            # Simuliere realistische Fahrzeugdaten
            import math
            
            elapsed = time.time() - self.current_session.start_time
            freq = 10.0  # 10 Hz Grundfrequenz
            
            # Simulierte Plattformposition (Sinuswelle)
            platform_pos = 3.0 * math.sin(2 * math.pi * freq * elapsed)
            
            # Simulierte Reifenkraft (mit Phase-Shift und Rauschen)
            phase_shift = math.radians(45)  # 45° Phase-Shift für "gute" Dämpfung
            force = 500 + 100 * math.sin(2 * math.pi * freq * elapsed + phase_shift) + 10 * (0.5 - time.time() % 1)
            
            # Erstelle simulierte CAN-Message
            sim_message = {
                "source": "simulator",
                "timestamp": time.time(),
                "arbitration_id": 0x08AAAA72,
                "data": [int(platform_pos * 10) & 0xFF, int(force) & 0xFF, int(force >> 8) & 0xFF],
                "is_extended_id": True,
                "platform_position": platform_pos,
                "tire_force": force
            }
            
            with self.queue_lock:
                self.message_queue.append(sim_message)
            
            self.message_count += 1
            self.last_message_time = time.time()
    
    async def _mqtt_message_loop(self):
        """MQTT-Message-Loop"""
        logger.info("MQTT-Message-Loop gestartet")
        
        while self.running:
            try:
                await asyncio.sleep(0.1)
                # MQTT-Messages werden über Callbacks verarbeitet
                
            except Exception as e:
                logger.error(f"Fehler in MQTT-Message-Loop: {e}")
                await asyncio.sleep(1.0)
        
        logger.info("MQTT-Message-Loop beendet")
    
    async def _data_processing_loop(self):
        """Datenverarbeitungs-Loop für Batch-Processing"""
        logger.info("Data-Processing-Loop gestartet")
        
        while self.running:
            try:
                # Auto-Save der aktuellen Session
                if (self.current_session and 
                    time.time() - self.current_session.start_time > self.auto_save_interval):
                    await self._auto_save_session_data()
                
                await asyncio.sleep(5.0)  # Weniger häufig als andere Loops
                
            except Exception as e:
                logger.error(f"Fehler in Data-Processing-Loop: {e}")
                await asyncio.sleep(5.0)
        
        logger.info("Data-Processing-Loop beendet")
    
    async def _heartbeat_loop(self):
        """Heartbeat-Loop"""
        heartbeat_interval = self.config.get(["bridge", "heartbeat_interval"], 30.0)
        
        while self.running:
            try:
                await self._send_heartbeat()
                await asyncio.sleep(heartbeat_interval)
                
            except Exception as e:
                logger.error(f"Heartbeat-Fehler: {e}")
                await asyncio.sleep(5.0)
    
    async def _send_status(self, status: str, message: str):
        """Sendet Status-Update"""
        await self.mqtt_handler.publish_async(
            "suspension/bridge/status",
            {
                "service": "enhanced_hardware_bridge",
                "status": status,
                "message": message,
                "mode": self.bridge_mode.value,
                "timestamp": time.time()
            }
        )
    
    async def _send_heartbeat(self):
        """Sendet Heartbeat mit detaillierten Informationen"""
        queue_size = len(self.message_queue)
        
        heartbeat_data = {
            "service": "enhanced_hardware_bridge",
            "timestamp": time.time(),
            "mode": self.bridge_mode.value,
            "running": self.running,
            "statistics": {
                "message_count": self.message_count,
                "queue_size": queue_size,
                "last_message_time": self.last_message_time,
                "active_session": self.current_session.session_id if self.current_session else None
            },
            "interfaces": {
                "hardware_can": self.can_interface is not None,
                "simulator_can": self.simulator_can_interface is not None,
                "mqtt": True  # MQTT ist immer verfügbar in diesem Context
            }
        }
        
        await self.mqtt_handler.publish_async(
            "suspension/system/heartbeat",
            heartbeat_data
        )
    
    async def _auto_save_session_data(self):
        """Auto-Save der aktuellen Session-Daten"""
        if not self.current_session:
            return
        
        # Zwischenspeicherung der Session-Daten
        session_data = {
            "session_id": self.current_session.session_id,
            "position": self.current_session.position,
            "start_time": self.current_session.start_time,
            "current_time": time.time(),
            "data_points": len(self.current_session.raw_data) if self.current_session.raw_data else 0
        }
        
        await self.mqtt_handler.publish_async(
            "suspension/test/session_update",
            session_data
        )
        
        logger.debug(f"Auto-Save für Session: {self.current_session.session_id}")
    
    async def _send_detailed_status(self):
        """Sendet detaillierten Status-Report"""
        status_report = {
            "service": "enhanced_hardware_bridge",
            "mode": self.bridge_mode.value,
            "running": self.running,
            "current_session": {
                "active": self.current_session is not None,
                "session_id": self.current_session.session_id if self.current_session else None,
                "position": self.current_session.position if self.current_session else None,
                "duration": time.time() - self.current_session.start_time if self.current_session else 0
            },
            "statistics": {
                "total_messages": self.message_count,
                "queue_size": len(self.message_queue),
                "session_history_count": len(self.session_history)
            },
            "interfaces": {
                "hardware_can_available": self.can_interface is not None,
                "simulator_can_available": self.simulator_can_interface is not None,
                "protocol_initialized": self.protocol is not None
            },
            "timestamp": time.time()
        }
        
        await self.mqtt_handler.publish_async(
            "suspension/bridge/detailed_status",
            status_report
        )
    
    async def _set_bridge_mode(self, mode: str):
        """Setzt neuen Bridge-Modus"""
        try:
            new_mode = BridgeMode(mode)
            if new_mode != self.bridge_mode:
                old_mode = self.bridge_mode
                self.bridge_mode = new_mode
                
                # Re-initialisiere CAN-Interfaces
                await self._init_can_interfaces()
                
                logger.info(f"Bridge-Modus geändert: {old_mode.value} → {new_mode.value}")
                
                await self.mqtt_handler.publish_async(
                    "suspension/bridge/mode_changed",
                    {
                        "old_mode": old_mode.value,
                        "new_mode": new_mode.value,
                        "timestamp": time.time()
                    }
                )
        except ValueError:
            logger.error(f"Ungültiger Bridge-Modus: {mode}")
    
    async def _clear_message_buffer(self):
        """Leert den Message-Buffer"""
        with self.queue_lock:
            cleared_count = len(self.message_queue)
            self.message_queue.clear()
        
        logger.info(f"Message-Buffer geleert: {cleared_count} Messages entfernt")
        
        await self.mqtt_handler.publish_async(
            "suspension/bridge/buffer_cleared",
            {
                "cleared_messages": cleared_count,
                "timestamp": time.time()
            }
        )
    
    async def _save_current_session(self):
        """Speichert aktuelle Session (für Debugging)"""
        if not self.current_session:
            return
        
        session_data = asdict(self.current_session)
        
        await self.mqtt_handler.publish_async(
            "suspension/bridge/session_saved",
            {
                "session_data": session_data,
                "timestamp": time.time()
            }
        )
        
        logger.info(f"Session gespeichert: {self.current_session.session_id}")


async def main():
    """Hauptfunktion für Enhanced Hardware Bridge"""
    # Logging konfigurieren
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('enhanced_hardware_bridge.log')
        ]
    )
    
    logger.info("Starte Enhanced Hardware Bridge...")
    
    # Command-line Arguments
    import argparse
    parser = argparse.ArgumentParser(description="Enhanced Hardware Bridge für Fahrwerkstester")
    parser.add_argument("--config", help="Pfad zur Konfigurationsdatei")
    parser.add_argument("--mode", choices=["hardware", "simulator", "hybrid"], 
                       help="Bridge-Modus überschreiben")
    parser.add_argument("--debug", action="store_true", help="Debug-Modus")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Bridge erstellen und starten
    bridge = EnhancedHardwareBridge(args.config)
    
    # Modus überschreiben falls angegeben
    if args.mode:
        bridge.bridge_mode = BridgeMode(args.mode)
        logger.info(f"Bridge-Modus überschrieben: {args.mode}")
    
    try:
        await bridge.start()
    except KeyboardInterrupt:
        logger.info("Bridge durch Benutzer unterbrochen")
    except Exception as e:
        logger.error(f"Bridge-Fehler: {e}")
    finally:
        await bridge.stop()


if __name__ == "__main__":
    asyncio.run(main())
