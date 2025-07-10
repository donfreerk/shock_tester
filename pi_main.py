#!/usr/bin/env python3
"""
🚀 Fahrwerkstester Pi Main Service
Intelligente Hauptdatei für Raspberry Pi Deployment

Features:
- Auto-Detection: CAN-Hardware vs. Simulator
- Service-Orchestrierung: Hardware Bridge + Pi Processing + MQTT
- Graceful Shutdown und Error Recovery
- Pi-optimierte Resource-Verwaltung
- Comprehensive Logging und Monitoring

Usage:
    python pi_main.py [options]

Options:
    --force-simulator    Zwinge Simulator-Modus
    --force-can          Zwinge CAN-Hardware-Modus
    --debug              Debug-Modus aktivieren
    --config PATH        Konfigurationsdatei
    --log-level LEVEL    Log-Level (DEBUG, INFO, WARNING, ERROR)
"""

import asyncio
import signal
import sys
import time
import logging
import argparse
import subprocess
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import importlib.util

# Pfad-Setup für Imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir / "common"))

# Zentrale Imports
try:
    from suspension_core.mqtt.handler import MqttHandler
    from suspension_core.config import ConfigManager
    from suspension_core.can.interface_factory import create_can_interface
    SUSPENSION_CORE_AVAILABLE = True
except ImportError as e:
    print(f"❌ Suspension Core nicht verfügbar: {e}")
    SUSPENSION_CORE_AVAILABLE = False

# Service-Imports
try:
    from backend.pi_processing_service.main import PiProcessingService
    PI_PROCESSING_AVAILABLE = True
except ImportError:
    PI_PROCESSING_AVAILABLE = False

try:
    from backend.can_simulator_service.command_controlled_main import CommandControlledSimulatorService
    SIMULATOR_AVAILABLE = True
except ImportError:
    SIMULATOR_AVAILABLE = False

try:
    from hardware.enhanced_hardware_bridge import EnhancedHardwareBridge
    HARDWARE_BRIDGE_AVAILABLE = True
except ImportError:
    HARDWARE_BRIDGE_AVAILABLE = False


class OperationMode(Enum):
    """Betriebsmodi des Pi-Systems"""
    CAN_HARDWARE = "can_hardware"
    SIMULATOR = "simulator"
    MIXED = "mixed"


@dataclass
class SystemStatus:
    """System-Status-Container"""
    mode: OperationMode
    can_available: bool
    mqtt_connected: bool
    services_running: Dict[str, bool]
    uptime: float
    errors: List[str]
    warnings: List[str]


class PiSystemManager:
    """
    Hauptmanager für das Pi-System

    Verantwortlichkeiten:
    - Hardware-Detection (CAN vs. Simulator)
    - Service-Lifecycle-Management
    - System-Monitoring und Health-Checks
    - Graceful Shutdown
    """

    def __init__(self, config_path: Optional[str] = None, force_mode: Optional[str] = None):
        """
        Initialisiert den Pi System Manager

        Args:
            config_path: Pfad zur Konfigurationsdatei
            force_mode: Erzwinge bestimmten Modus ('can' oder 'simulator')
        """
        self.config_path = config_path
        self.force_mode = force_mode
        self.running = False
        self.start_time = None

        # System-Status
        self.system_status = SystemStatus(
            mode=OperationMode.SIMULATOR,
            can_available=False,
            mqtt_connected=False,
            services_running={},
            uptime=0.0,
            errors=[],
            warnings=[]
        )

        # Service-Container
        self.services = {}
        self.service_tasks = {}

        # Setup logging
        self.setup_logging()

        # Konfiguration laden
        self.load_configuration()

        # Signal handlers (Windows-kompatibel)
        if not sys.platform.startswith('win'):
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)

    def setup_logging(self):
        """Konfiguriert das Logging für Pi-Umgebung (Unicode-Safe)"""
        log_level = logging.INFO

        # Pi-spezifische Log-Konfiguration
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        # Console Handler mit UTF-8-Support
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)

        # Windows-spezifische UTF-8-Behandlung
        if sys.platform.startswith('win'):
            try:
                # Versuche UTF-8 zu erzwingen für Windows
                if hasattr(console_handler.stream, 'reconfigure'):
                    console_handler.stream.reconfigure(encoding='utf-8')
            except Exception:
                pass  # Fallback zu Standard-Encoding

        console_handler.setFormatter(logging.Formatter(log_format))

        # File Handler für Pi/Windows
        if sys.platform.startswith('win'):
            log_dir = Path("logs")
            log_file = log_dir / "pi_main.log"
        else:
            log_dir = Path("/var/log/fahrwerkstester")
            log_file = log_dir / "pi_main.log"

        log_dir.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(log_format))

        # Root Logger konfigurieren
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        # Clear existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Add new handlers
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)

        self.logger = logging.getLogger(__name__)
        self.logger.info("Pi System Manager Logging initialisiert")

    def load_configuration(self):
        """Lädt die System-Konfiguration"""
        try:
            if SUSPENSION_CORE_AVAILABLE:
                self.config = ConfigManager(self.config_path)
                self.logger.info("✅ Konfiguration geladen")
            else:
                # Fallback-Konfiguration
                self.config = {
                    "mqtt": {"broker": "localhost", "port": 1883},
                    "can": {"interface": "can0", "bitrate": 500000},
                    "system": {"heartbeat_interval": 30.0}
                }
                self.logger.warning("⚠️ Fallback-Konfiguration verwendet")
        except Exception as e:
            self.logger.error(f"❌ Konfiguration konnte nicht geladen werden: {e}")
            self.system_status.errors.append(f"Config load failed: {e}")

    def detect_hardware_capabilities(self) -> OperationMode:
        """
        Erkennt verfügbare Hardware-Capabilities

        Returns:
            OperationMode basierend auf verfügbarer Hardware
        """
        self.logger.info("🔍 Erkenne Hardware-Capabilities...")

        # Force-Modus prüfen
        if self.force_mode:
            if self.force_mode == "can":
                self.logger.info("🔧 CAN-Modus erzwungen")
                return OperationMode.CAN_HARDWARE
            elif self.force_mode == "simulator":
                self.logger.info("🔧 Simulator-Modus erzwungen")
                return OperationMode.SIMULATOR

        # CAN-Hardware-Detection
        can_available = self.check_can_hardware()

        if can_available:
            self.logger.info("✅ CAN-Hardware erkannt - verwende Hardware-Modus")
            self.system_status.can_available = True
            return OperationMode.CAN_HARDWARE
        else:
            self.logger.info("⚠️ Keine CAN-Hardware - verwende Simulator-Modus")
            self.system_status.can_available = False
            return OperationMode.SIMULATOR

    def check_can_hardware(self) -> bool:
        """
        Prüft, ob CAN-Hardware verfügbar ist (Windows-kompatibel)

        Returns:
            True wenn CAN-Hardware verfügbar
        """
        try:
            # Windows-Check: CAN-Hardware normalerweise nicht verfügbar
            if sys.platform.startswith('win'):
                self.logger.debug("Windows-System erkannt - CAN-Hardware nicht verfügbar")
                return False

            # Linux/Pi: Echte CAN-Hardware-Prüfung
            # Methode 1: Prüfe /sys/class/net für CAN-Interfaces
            can_interfaces = list(Path("/sys/class/net").glob("can*"))
            if can_interfaces:
                self.logger.debug(f"CAN-Interfaces gefunden: {[i.name for i in can_interfaces]}")

                # Methode 2: Prüfe ob Interface aktiv ist
                for interface in can_interfaces:
                    if self.is_can_interface_active(interface.name):
                        self.logger.info(f"Aktives CAN-Interface: {interface.name}")
                        return True

            # Methode 3: Prüfe mit ip link
            result = subprocess.run(
                ["ip", "link", "show", "type", "can"],
                capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0 and "can" in result.stdout:
                self.logger.debug("CAN-Interface via ip link gefunden")
                return True

            # Methode 4: Prüfe ob vcan0 erstellt werden kann (für Testing)
            if os.path.exists("/sys/class/net/vcan0"):
                self.logger.debug("Virtual CAN-Interface gefunden")
                return True

            return False

        except Exception as e:
            self.logger.warning(f"CAN-Hardware-Prüfung fehlgeschlagen: {e}")
            return False

    def is_can_interface_active(self, interface_name: str) -> bool:
        """Prüft, ob ein CAN-Interface aktiv ist"""
        try:
            operstate_file = Path(f"/sys/class/net/{interface_name}/operstate")
            if operstate_file.exists():
                state = operstate_file.read_text().strip()
                return state == "up"
            return False
        except Exception:
            return False

    async def start_system(self):
        """Startet das komplette Pi-System"""
        self.logger.info("🚀 Starte Pi-System...")

        if not SUSPENSION_CORE_AVAILABLE:
            self.logger.error("❌ Suspension Core nicht verfügbar - kann nicht starten")
            return False

        self.running = True
        self.start_time = time.time()

        try:
            # Hardware-Modus erkennen
            self.system_status.mode = self.detect_hardware_capabilities()

            # MQTT-Verbindung aufbauen
            if not await self.setup_mqtt():
                self.logger.error("❌ MQTT-Setup fehlgeschlagen")
                return False

            # Services basierend auf Modus starten
            if self.system_status.mode == OperationMode.CAN_HARDWARE:
                await self.start_can_mode_services()
            else:
                await self.start_simulator_mode_services()

            # System-Monitoring starten
            await self.start_monitoring()

            self.logger.info(f"✅ Pi-System gestartet im {self.system_status.mode.value} Modus")
            return True

        except Exception as e:
            self.logger.error(f"❌ System-Start fehlgeschlagen: {e}")
            self.system_status.errors.append(f"System start failed: {e}")
            return False

    async def setup_mqtt(self) -> bool:
        """Stellt MQTT-Verbindung her"""
        try:
            self.mqtt_handler = MqttHandler(
                client_id=f"pi_main_{int(time.time())}",
                host=self.config.get("mqtt.broker", "localhost"),
                port=self.config.get("mqtt.port", 1883),
                app_type="pi_main"
            )

            # MQTT-Handler connect() ist nicht async - kein await verwenden!
            connected = self.mqtt_handler.connect(timeout=10.0)

            if connected:
                self.system_status.mqtt_connected = True
                self.logger.info("✅ MQTT-Verbindung hergestellt")

                # System-Status publizieren
                await self.publish_system_status()
                return True
            else:
                self.logger.error("❌ MQTT-Verbindung fehlgeschlagen")
                return False

        except Exception as e:
            self.logger.error(f"❌ MQTT-Setup fehlgeschlagen: {e}")
            return False

    async def start_can_mode_services(self):
        """Startet Services für CAN-Hardware-Modus"""
        self.logger.info("🔧 Starte CAN-Hardware-Services...")

        # Hardware Bridge Service
        if HARDWARE_BRIDGE_AVAILABLE:
            try:
                self.services["hardware_bridge"] = EnhancedHardwareBridge(
                    mqtt_handler=self.mqtt_handler,
                    config=self.config
                )

                self.service_tasks["hardware_bridge"] = asyncio.create_task(
                    self.services["hardware_bridge"].start()
                )

                self.system_status.services_running["hardware_bridge"] = True
                self.logger.info("✅ Hardware Bridge Service gestartet")

            except Exception as e:
                self.logger.error(f"❌ Hardware Bridge Service fehlgeschlagen: {e}")
                self.system_status.errors.append(f"Hardware Bridge failed: {e}")

        # Pi Processing Service
        await self.start_pi_processing_service()

    async def start_simulator_mode_services(self):
        """Startet Services für Simulator-Modus"""
        self.logger.info("🔧 Starte Simulator-Services...")

        # CAN Simulator Service
        if SIMULATOR_AVAILABLE:
            try:
                self.services["can_simulator"] = CommandControlledSimulatorService(
                    broker=self.config.get("mqtt.broker", "localhost"),
                    port=self.config.get("mqtt.port", 1883)
                )

                self.service_tasks["can_simulator"] = asyncio.create_task(
                    self.services["can_simulator"].start()
                )

                self.system_status.services_running["can_simulator"] = True
                self.logger.info("✅ CAN Simulator Service gestartet")

            except Exception as e:
                self.logger.error(f"❌ CAN Simulator Service fehlgeschlagen: {e}")
                self.system_status.errors.append(f"CAN Simulator failed: {e}")

        # Pi Processing Service
        await self.start_pi_processing_service()

    async def start_pi_processing_service(self):
        """Startet Pi Processing Service (in beiden Modi)"""
        if PI_PROCESSING_AVAILABLE:
            try:
                self.services["pi_processing"] = PiProcessingService(
                    config_path=self.config_path
                )

                self.service_tasks["pi_processing"] = asyncio.create_task(
                    self.services["pi_processing"].start()
                )

                self.system_status.services_running["pi_processing"] = True
                self.logger.info("✅ Pi Processing Service gestartet")

            except Exception as e:
                self.logger.error(f"❌ Pi Processing Service fehlgeschlagen: {e}")
                self.system_status.errors.append(f"Pi Processing failed: {e}")

    async def start_monitoring(self):
        """Startet System-Monitoring"""
        self.service_tasks["monitoring"] = asyncio.create_task(
            self.monitoring_loop()
        )
        self.logger.info("✅ System-Monitoring gestartet")

    async def monitoring_loop(self):
        """Hauptschleife für System-Monitoring"""
        while self.running:
            try:
                # System-Status aktualisieren
                await self.update_system_status()

                # Health-Check für Services
                await self.check_service_health()

                # Status publizieren
                await self.publish_system_status()

                # Warte für nächsten Zyklus
                await asyncio.sleep(self.config.get("system.heartbeat_interval", 30.0))

            except Exception as e:
                self.logger.error(f"❌ Monitoring-Fehler: {e}")
                await asyncio.sleep(5.0)  # Kurze Pause bei Fehlern

    async def update_system_status(self):
        """Aktualisiert den System-Status"""
        if self.start_time:
            self.system_status.uptime = time.time() - self.start_time

        # Service-Status prüfen
        for service_name, task in self.service_tasks.items():
            if task and not task.done():
                self.system_status.services_running[service_name] = True
            else:
                self.system_status.services_running[service_name] = False
                if service_name != "monitoring":  # Monitoring sich selbst nicht prüfen
                    self.logger.warning(f"⚠️ Service {service_name} ist nicht aktiv")

    async def check_service_health(self):
        """Prüft Health-Status aller Services"""
        for service_name, service in self.services.items():
            try:
                if hasattr(service, 'health_check'):
                    health = await service.health_check()
                    if not health.get('healthy', False):
                        self.logger.warning(f"⚠️ Service {service_name} nicht gesund: {health}")
                        self.system_status.warnings.append(f"{service_name} unhealthy")

            except Exception as e:
                self.logger.error(f"❌ Health-Check für {service_name} fehlgeschlagen: {e}")

    async def publish_system_status(self):
        """Publiziert System-Status über MQTT"""
        if self.system_status.mqtt_connected and hasattr(self, 'mqtt_handler'):
            try:
                status_data = {
                    "mode": self.system_status.mode.value,
                    "can_available": self.system_status.can_available,
                    "mqtt_connected": self.system_status.mqtt_connected,
                    "services_running": self.system_status.services_running,
                    "uptime": self.system_status.uptime,
                    "errors": self.system_status.errors[-5:],  # Nur letzte 5 Fehler
                    "warnings": self.system_status.warnings[-5:],  # Nur letzte 5 Warnungen
                    "timestamp": time.time()
                }

                self.mqtt_handler.publish(
                    "suspension/system/pi_status",
                    status_data
                )

            except Exception as e:
                self.logger.error(f"❌ Status-Publishing fehlgeschlagen: {e}")

    async def shutdown(self):
        """Graceful Shutdown des Systems"""
        self.logger.info("🛑 Starte System-Shutdown...")
        self.running = False

        # Services stoppen
        for service_name, task in self.service_tasks.items():
            if task and not task.done():
                self.logger.info(f"🛑 Stoppe {service_name}...")
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Services cleanup
        for service_name, service in self.services.items():
            if hasattr(service, 'stop'):
                try:
                    await service.stop()
                    self.logger.info(f"✅ {service_name} gestoppt")
                except Exception as e:
                    self.logger.error(f"❌ Fehler beim Stoppen von {service_name}: {e}")

        # MQTT-Verbindung schließen
        if hasattr(self, 'mqtt_handler'):
            self.mqtt_handler.disconnect()

        self.logger.info("✅ System-Shutdown abgeschlossen")

    def signal_handler(self, signum, frame):
        """Signal-Handler für graceful shutdown"""
        self.logger.info(f"🛑 Signal {signum} empfangen - starte Shutdown...")
        asyncio.create_task(self.shutdown())

    async def run(self):
        """Hauptlaufschleife"""
        if not await self.start_system():
            return False

        try:
            self.logger.info("🎯 Pi-System läuft - drücke Ctrl+C zum Beenden")

            # Warte auf Shutdown-Signal
            while self.running:
                await asyncio.sleep(1.0)

        except KeyboardInterrupt:
            self.logger.info("🛑 Shutdown durch Benutzer")
        except Exception as e:
            self.logger.error(f"❌ Unerwarteter Fehler: {e}")
        finally:
            await self.shutdown()

        return True


def setup_argument_parser():
    """Konfiguriert Argument Parser"""
    parser = argparse.ArgumentParser(
        description="🚀 Fahrwerkstester Pi Main Service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
    python pi_main.py                    # Auto-Detection
    python pi_main.py --force-simulator  # Zwinge Simulator
    python pi_main.py --force-can        # Zwinge CAN-Hardware
    python pi_main.py --debug            # Debug-Modus
        """
    )

    parser.add_argument(
        "--force-simulator",
        action="store_true",
        help="Zwinge Simulator-Modus (auch wenn CAN-Hardware verfügbar)"
    )

    parser.add_argument(
        "--force-can",
        action="store_true",
        help="Zwinge CAN-Hardware-Modus (auch wenn nicht erkannt)"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Debug-Modus aktivieren"
    )

    parser.add_argument(
        "--config",
        type=str,
        help="Pfad zur Konfigurationsdatei"
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log-Level setzen"
    )

    return parser


def check_dependencies():
    """Prüft verfügbare Abhängigkeiten"""
    print("🔍 Prüfe System-Abhängigkeiten...")

    dependencies = {
        "Suspension Core": SUSPENSION_CORE_AVAILABLE,
        "Pi Processing Service": PI_PROCESSING_AVAILABLE,
        "CAN Simulator": SIMULATOR_AVAILABLE,
        "Hardware Bridge": HARDWARE_BRIDGE_AVAILABLE
    }

    all_available = True
    for name, available in dependencies.items():
        status = "✅" if available else "❌"
        print(f"  {status} {name}")
        if not available:
            all_available = False

    if not all_available:
        print("\n⚠️ Einige Abhängigkeiten fehlen - Funktionalität kann eingeschränkt sein")

    return all_available


async def main():
    """Hauptfunktion"""
    print("🚀 Fahrwerkstester Pi Main Service")
    print("=" * 50)

    # Abhängigkeiten prüfen
    check_dependencies()

    # Argumente parsen
    parser = setup_argument_parser()
    args = parser.parse_args()

    # Force-Modus bestimmen
    force_mode = None
    if args.force_simulator:
        force_mode = "simulator"
    elif args.force_can:
        force_mode = "can"

    # System Manager erstellen
    system_manager = PiSystemManager(
        config_path=args.config,
        force_mode=force_mode
    )

    # System starten
    success = await system_manager.run()

    if success:
        print("✅ System erfolgreich beendet")
        return 0
    else:
        print("❌ System mit Fehlern beendet")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        print(f"❌ Kritischer Fehler: {e}")
        sys.exit(1)
