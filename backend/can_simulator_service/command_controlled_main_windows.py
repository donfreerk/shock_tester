#!/usr/bin/env python3
"""
Command-Controlled CAN Simulator Service - Windows-kompatible Version
Ohne Unicode-Emojis für cmd/PowerShell Kompatibilität
"""

# Alle Emojis durch ASCII ersetzen
import os
import sys

# UTF-8 Encoding für Windows setzen
if sys.platform.startswith('win'):
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# Restlicher Code ist identisch, aber mit ASCII statt Emojis
import asyncio
import time
import signal
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

# Pfad-Setup für Imports
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

try:
    from backend.can_simulator_service.core.egea_simulator import EGEASimulator
    from backend.can_simulator_service.mqtt.simulator_adapter import SimulatorMqttAdapter
    from common.suspension_core.mqtt.handler import MqttHandler
    from common.suspension_core.config import ConfigManager
except ImportError as e:
    print(f"Import-Fehler: {e}")
    print("Stelle sicher, dass du im Projekt-Root-Verzeichnis bist")
    print("Überprüfe, dass alle Module in der korrekten Struktur existieren:")
    print("  - backend/can_simulator_service/core/egea_simulator.py")
    print("  - backend/can_simulator_service/mqtt/simulator_adapter.py")
    print("  - common/suspension_core/mqtt/handler.py")
    print("  - common/suspension_core/config/manager.py")
    sys.exit(1)

# Logger Setup
logger = logging.getLogger(__name__)

@dataclass
class TestSession:
    """Beschreibt eine laufende Test-Session"""
    test_id: str
    position: str
    method: str
    duration: float
    start_time: float
    quality: str = "good"
    active: bool = True

class CommandControlledSimulatorService:
    """
    CAN Simulator Service - reagiert auf GUI-Kommandos
    Startet Tests nur auf Aufforderung, läuft nicht endlos
    """
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        broker: str = "localhost",
        port: int = 1883,
    ):
        """Initialisiert den kommando-gesteuerten Simulator Service"""
        # Konfiguration laden
        self.config = ConfigManager(config_path) if config_path else None

        # EGEA-Simulator initialisieren
        self.simulator = EGEASimulator()

        # MQTT-Handler für Kommandos
        self.mqtt_handler = MqttHandler(
            host=broker,  # host= statt broker=
            port=port,
            client_id=f"can_simulator_command_{int(time.time())}",
            app_type="simulator"
        )

        # MQTT-Adapter für Datenübertragung (falls verfügbar)
        try:
            self.mqtt_adapter = SimulatorMqttAdapter(self.simulator, self.mqtt_handler)
        except Exception as e:
            logger.warning(f"MQTT-Adapter konnte nicht initialisiert werden: {e}")
            self.mqtt_adapter = None

        # Service-Status
        self.running = False
        self.current_test: Optional[TestSession] = None

        # Graceful Shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("Command-Controlled Simulator Service initialisiert")

    def _signal_handler(self, signum, frame):
        """Behandelt Shutdown-Signale"""
        logger.info(f"Signal {signum} empfangen, beende Service...")
        self.running = False

    def _setup_command_handlers(self):
        """Registriert MQTT-Command-Handler"""

        # Test-Kommandos von der GUI
        self.mqtt_handler.subscribe("suspension/test/command", self._handle_test_command)

        # Simulator-spezifische Kommandos
        self.mqtt_handler.subscribe(
            "suspension/simulator/command", self._handle_simulator_command
        )

        logger.info("Command-Handler registriert")

    def _handle_test_command(self, topic: str, message: Dict[str, Any]):
        """Verarbeitet Test-Kommandos von der GUI"""
        try:
            command = message.get("command")

            if command == "start_test":
                self._start_test_from_command(message)
            elif command == "stop_test":
                self._stop_current_test()
            else:
                logger.warning(f"Unbekanntes Test-Kommando: {command}")

        except Exception as e:
            logger.error(f"Fehler beim Verarbeiten von Test-Kommando: {e}")
            self._publish_error_status(str(e))

    def _handle_simulator_command(self, topic: str, message: Dict[str, Any]):
        """Verarbeitet Simulator-spezifische Kommandos"""
        try:
            command = message.get("command")

            if command == "set_quality":
                quality = message.get("quality", "good")
                self.simulator.set_damping_quality(quality)
                logger.info(f"Dämpfungsqualität gesetzt: {quality}")

            elif command == "get_status":
                self._publish_service_status()

            elif command == "reset":
                self._reset_simulator()

        except Exception as e:
            logger.error(f"Fehler beim Verarbeiten von Simulator-Kommando: {e}")

    def _start_test_from_command(self, message: Dict[str, Any]):
        """Startet einen Test basierend auf GUI-Kommando"""

        # Prüfen ob bereits ein Test läuft
        if self.current_test and self.current_test.active:
            logger.warning("Test bereits aktiv - stoppe vorherigen Test")
            self._stop_current_test()

        # Parameter extrahieren
        params = message.get("parameters", {})
        position = params.get("position", "front_right")
        method = params.get("method", "phase_shift")
        duration = float(params.get("duration", 30.0))
        quality = params.get("quality", "good")

        # Test-ID generieren
        test_id = f"test_{int(time.time())}_{position}"

        # Neue Test-Session erstellen
        self.current_test = TestSession(
            test_id=test_id,
            position=position,
            method=method,
            duration=duration,
            start_time=time.time(),
            quality=quality,
            active=True,
        )

        # Simulator konfigurieren
        self.simulator.set_damping_quality(quality)

        # Test starten
        side = "left" if "left" in position else "right"
        self.simulator.start_test(side, duration)

        # Status publizieren
        self._publish_test_status("started")

        logger.info(f"[START] Test gestartet: {test_id} ({method} @ {position} für {duration}s)")

    def _stop_current_test(self):
        """Stoppt den aktuell laufenden Test"""
        if self.current_test and self.current_test.active:
            # Simulator stoppen
            self.simulator.stop_test()

            # Test-Session beenden
            self.current_test.active = False

            # Status publizieren
            self._publish_test_status("stopped")

            logger.info(f"[STOP] Test gestoppt: {self.current_test.test_id}")

            # Session zurücksetzen
            self.current_test = None

    def _reset_simulator(self):
        """Setzt den Simulator zurück"""
        if self.current_test:
            self._stop_current_test()

        # Simulator zurücksetzen (falls Methode verfügbar)
        if hasattr(self.simulator, "reset"):
            self.simulator.reset()

        logger.info("[RESET] Simulator zurückgesetzt")

    def _publish_test_status(self, status: str):
        """Publiziert Test-Status"""
        if not self.current_test:
            return

        status_message = {
            "test_id": self.current_test.test_id,
            "status": status,
            "position": self.current_test.position,
            "method": self.current_test.method,
            "duration": self.current_test.duration,
            "elapsed": time.time() - self.current_test.start_time
            if status != "started"
            else 0,
            "timestamp": time.time(),
            "source": "simulator",
        }

        self.mqtt_handler.publish("suspension/test/status", status_message)
        logger.debug(f"[STATUS] Test-Status publiziert: {status}")

    def _publish_service_status(self):
        """Publiziert Service-Status"""
        status = {
            "service": "can_simulator",
            "status": "running" if self.running else "stopped",
            "current_test": {
                "active": self.current_test.active if self.current_test else False,
                "test_id": self.current_test.test_id if self.current_test else None,
                "position": self.current_test.position if self.current_test else None,
            }
            if self.current_test
            else None,
            "timestamp": time.time(),
        }

        self.mqtt_handler.publish("suspension/system/heartbeat", status)
        logger.debug("[HEARTBEAT] Heartbeat gesendet")

    def _publish_error_status(self, error_message: str):
        """Publiziert Fehler-Status"""
        error_status = {
            "service": "can_simulator",
            "status": "error",
            "error": error_message,
            "timestamp": time.time(),
        }

        self.mqtt_handler.publish("suspension/system/error", error_status)
        logger.error(f"[ERROR] Fehler publiziert: {error_message}")

    async def start(self):
        """Startet den Service"""
        logger.info("[STARTUP] Starte Command-Controlled Simulator Service...")
        self.running = True

        try:
            # MQTT verbinden
            if not self.mqtt_handler.connect():
                raise RuntimeError("MQTT-Verbindung fehlgeschlagen")

            # Command-Handler registrieren
            self._setup_command_handlers()

            logger.info("[OK] MQTT verbunden - warte auf Kommandos...")
            logger.info("[INFO] Abonnierte Topics:")
            logger.info("   - suspension/test/command (GUI-Kommandos)")
            logger.info("   - suspension/simulator/command (Simulator-Kommandos)")

            # Hauptschleife - wartet auf Kommandos und überwacht Tests
            await self._main_loop()

        except Exception as e:
            logger.error(f"[FAIL] Fehler beim Starten des Services: {e}")
            raise
        finally:
            await self.shutdown()

    async def _main_loop(self):
        """Hauptschleife - überwacht laufende Tests und verarbeitet Kommandos"""
        last_heartbeat = 0
        last_status_log = 0

        while self.running:
            try:
                current_time = time.time()

                # Heartbeat senden (alle 5 Sekunden)
                if current_time - last_heartbeat > 5.0:
                    self._publish_service_status()
                    last_heartbeat = current_time

                # Status-Log (alle 30 Sekunden wenn kein Test läuft)
                if not self.current_test and current_time - last_status_log > 30.0:
                    logger.info("[WAIT] Warte auf Test-Kommandos...")
                    last_status_log = current_time

                # Aktuellen Test überwachen
                if self.current_test and self.current_test.active:
                    elapsed = current_time - self.current_test.start_time

                    # Test-Ende prüfen
                    if elapsed >= self.current_test.duration:
                        logger.info(f"[TIMEOUT] Test-Zeit abgelaufen: {self.current_test.test_id}")
                        self._stop_current_test()
                        self._publish_test_status("completed")

                    # Test-Daten generieren (falls Simulator aktiv)
                    elif self.simulator.test_active:
                        data_point = self.simulator.generate_data_point()
                        if data_point:
                            # Live-Status alle 3 Sekunden loggen
                            if int(elapsed) % 3 == 0:
                                logger.info(f"[DATA] [{elapsed:5.1f}s] {data_point.frequency:5.1f}Hz, {data_point.phase_shift:5.1f}°")

                # Kurze Pause um CPU zu schonen
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"[LOOP-ERROR] Fehler in Hauptschleife: {e}")
                await asyncio.sleep(1.0)

        logger.info("[FINISHED] Hauptschleife beendet")

    async def shutdown(self):
        """Beendet den Service gracefully"""
        logger.info("[SHUTDOWN] Beende Command-Controlled Simulator Service...")

        # Laufenden Test stoppen
        if self.current_test and self.current_test.active:
            self._stop_current_test()

        # Simulator stoppen
        if (
            self.simulator
            and hasattr(self.simulator, "test_active")
            and self.simulator.test_active
        ):
            self.simulator.stop_test()

        # MQTT-Verbindungen trennen
        if self.mqtt_adapter:
            try:
                self.mqtt_adapter.disconnect()
            except:
                pass

        if self.mqtt_handler:
            self.mqtt_handler.disconnect()

        logger.info("[OK] Service beendet")


def setup_logging(log_level: str = "INFO", debug: bool = False):
    """Konfiguriert das Logging-System"""
    if debug:
        log_level = "DEBUG"

    level = getattr(logging, log_level.upper(), logging.INFO)

    # Logging-Format ohne Emojis
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Basis-Konfiguration
    logging.basicConfig(level=level, format=log_format, datefmt="%Y-%m-%d %H:%M:%S")

    # MQTT-Client-Logs reduzieren (nur Warnings und Errors)
    logging.getLogger("paho.mqtt.client").setLevel(logging.WARNING)


def parse_arguments():
    """Parst Kommandozeilen-Argumente"""
    parser = argparse.ArgumentParser(
        description="Command-Controlled CAN Simulator Service (Windows-kompatibel)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  %(prog)s                              # Standard-Start
  %(prog)s --debug                      # Mit Debug-Ausgaben
  %(prog)s --broker 192.168.1.100       # Anderer MQTT-Broker
  %(prog)s --config config/sim.yaml     # Eigene Konfiguration
        """,
    )

    parser.add_argument("--config", type=str, help="Pfad zur Konfigurationsdatei")
    parser.add_argument("--debug", action="store_true", help="Debug-Modus aktivieren")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log-Level setzen (default: INFO)",
    )
    parser.add_argument(
        "--broker",
        type=str,
        default="localhost",
        help="MQTT-Broker-Host (default: localhost)",
    )
    parser.add_argument(
        "--port", type=int, default=1883, help="MQTT-Broker-Port (default: 1883)"
    )

    return parser.parse_args()


async def main():
    """Haupteinstiegspunkt"""
    args = parse_arguments()

    # Logging konfigurieren
    setup_logging(args.log_level, args.debug)

    try:
        # Service erstellen und starten
        service = CommandControlledSimulatorService(
            config_path=args.config, broker=args.broker, port=args.port
        )

        # Banner anzeigen (ohne Emojis)
        print("=" * 60)
        print("EGEA Command-Controlled Simulator Service")
        print("=" * 60)
        print(f"MQTT-Broker: {args.broker}:{args.port}")
        print("Wartet auf Test-Kommandos von der GUI...")
        print("Test-Topic: suspension/test/command")
        print("Simulator-Topic: suspension/simulator/command")
        print("=" * 60)
        print("Beispiel-Kommando:")
        print("   Topic: suspension/test/command")
        print('   Payload: {"command": "start_test", "parameters": {')
        print('     "position": "front_right", "duration": 30, "method": "phase_shift"}}')
        print("=" * 60)
        print("Druecke Ctrl+C zum Beenden")
        print()

        await service.start()

    except KeyboardInterrupt:
        logger.info("[USER] Service durch Benutzer beendet")
    except Exception as e:
        logger.error(f"[FATAL] Service-Fehler: {e}")
        return 1

    return 0


if __name__ == "__main__":
    # Eventloop starten
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n[STOP] Service unterbrochen")
        sys.exit(0)