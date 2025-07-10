# backend/can_simulator_service/main.py
"""
EGEA CAN-Simulator Service - Haupteinstiegspunkt
Application Layer - orchestriert Core Domain und Infrastructure

Neue, schlanke Implementierung nach hexagonaler Architektur:
- Trennt Domain-Logik (EGEASimulator) von Infrastructure (MQTT)
- Unterstützt Dependency Injection
- Einfache Konfiguration und bessere Testbarkeit
"""

import argparse
import asyncio
import logging
import signal
import sys
import time
from pathlib import Path
import itertools

import logger

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from common.suspension_core.config.config_model import settings
from suspension_core.mqtt import MqttHandler
from suspension_core.mqtt.service import MqttServiceBase, MqttTopics

# Lazy imports to avoid circular dependencies
try:
    from backend.can_simulator_service.core.egea_simulator import EGEASimulator
    from backend.can_simulator_service.core.config import TestConfiguration
    from backend.can_simulator_service.mqtt import SimulatorMqttAdapter
except ImportError as e:
    logger.warning(f"Some simulator components not available: {e}")
    EGEASimulator = None
    TestConfiguration = None
    SimulatorMqttAdapter = None

logger = logging.getLogger(__name__)


class SimulatorService:
    """
    Hauptservice für EGEA-Simulator

    Orchestriert alle Komponenten und verwaltet den Lebenszyklus
    """

    def __init__(
        self,
        config=None,
        endless_mode=False,
        auto_test=False,
        test_duration=30.0,
        endless_pause=3.0,
    ):
        """Initialisiert Simulator-Service"""
        if TestConfiguration:
            self.config = config or TestConfiguration()
        else:
            self.config = config or {}
        self.running = False

        # Endless/Auto-Test Parameter
        self.endless_mode = endless_mode
        self.auto_test = auto_test
        self.test_duration = test_duration
        self.endless_pause = endless_pause

        # Test-Variationen für Endlos-Modus
        if self.endless_mode:
            self.qualities = itertools.cycle(
                ["excellent", "good", "acceptable", "poor"]
            )
            self.sides = itertools.cycle(["left", "right"])

        # Core-Komponenten
        self.simulator = None
        self.mqtt_handler = None
        self.mqtt_adapter = None

        # Signal-Handler für graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Behandelt Shutdown-Signale"""
        logger.info(f"Signal {signum} empfangen, beende Service...")
        self.running = False

    async def initialize(self):
        """Initialisiert alle Service-Komponenten"""
        try:
            logger.info("Initialisiere EGEA-Simulator Service...")

            # 1. Core Simulator erstellen
            self.simulator = EGEASimulator(config=self.config)
            logger.info("EGEA-Simulator initialisiert")

            # 2. MQTT-Handler erstellen
            self.mqtt_handler = MqttHandler(
                client_id="egea_simulator",
                host=settings.mqtt.broker,
                port=settings.mqtt.port,
                username=settings.mqtt.username,
                password=settings.mqtt.password,
                app_type="simulator",
            )

            # MQTT verbinden
            if not await self._connect_mqtt():
                raise RuntimeError("MQTT-Verbindung fehlgeschlagen")

            # 3. MQTT-Adapter erstellen (verbindet Core mit Infrastructure)
            self.mqtt_adapter = SimulatorMqttAdapter(
                simulator=self.simulator, mqtt_handler=self.mqtt_handler
            )
            logger.info("MQTT-Adapter initialisiert")

            logger.info("Service-Initialisierung abgeschlossen")

        except Exception as e:
            logger.error(f"Fehler bei Service-Initialisierung: {e}")
            raise

    async def _connect_mqtt(self) -> bool:
        """Stellt MQTT-Verbindung her"""
        try:
            logger.info(
                f"Verbinde zu MQTT-Broker: {settings.mqtt.broker}:{settings.mqtt.port}"
            )

            success = self.mqtt_handler.connect()
            if success:
                logger.info("MQTT-Verbindung erfolgreich")
                return True
            else:
                logger.error("MQTT-Verbindung fehlgeschlagen")
                return False

        except Exception as e:
            logger.error(f"MQTT-Verbindungsfehler: {e}")
            return False

    async def run(self):
        """Hauptservice-Loop"""
        self.running = True
        logger.info("EGEA-Simulator Service gestartet")

        # Service-Status publizieren
        if self.mqtt_adapter:
            self.mqtt_adapter._publish_system_status("ready", "Service gestartet")

        # Auto-Test oder Endlos-Modus starten
        if self.auto_test:
            logger.info(f"🚀 Auto-Test startet: {self.test_duration}s")
            self.simulator.start_test("left", self.test_duration)
        elif self.endless_mode:
            logger.info("🔄 Endlos-Modus aktiviert")
            await self._run_endless_tests()
            return  # Endlos-Modus hat eigene Loop

        try:
            while self.running:
                # Simulationsdaten generieren falls Test aktiv
                if self.simulator and self.simulator.test_active:
                    data_point = self.simulator.generate_data_point()
                    # Events werden automatisch über den Adapter publiziert

                # Heartbeat senden
                if self.mqtt_adapter:
                    self.mqtt_adapter.publish_heartbeat()

                # Kurze Pause (100Hz Sample Rate)
                await asyncio.sleep(0.01)  # 10ms = 100Hz

        except Exception as e:
            logger.error(f"Fehler im Service-Loop: {e}")
            raise
        finally:
            await self.shutdown()

    async def _run_endless_tests(self):
        """Führt endlos Tests durch"""
        logger.info("🔄 ENDLOS-TESTS gestartet - Ctrl+C zum Beenden")
        logger.info(f"⏱️  Test-Dauer: {self.test_duration}s")
        logger.info(f"⏸️  Pause: {self.endless_pause}s")

        test_count = 0

        try:
            while self.running:
                test_count += 1

                # Nächste Test-Parameter
                quality = next(self.qualities)
                side = next(self.sides)

                logger.info(f"🧪 TEST #{test_count}: {quality} {side}")

                # Dämpfungsqualität setzen
                self.simulator.set_damping_quality(quality)
                await asyncio.sleep(0.5)

                # Test starten
                self.simulator.start_test(side, self.test_duration)

                # Service-Loop während Test läuft
                test_start = time.time()
                while self.simulator.test_active and self.running:
                    # Simulationsdaten generieren
                    data_point = self.simulator.generate_data_point()
                    if data_point:
                        elapsed = time.time() - test_start
                        # Live-Anzeige alle 2 Sekunden
                        if int(elapsed) % 2 == 0:
                            logger.info(
                                f"📊 [{elapsed:5.1f}s] {data_point.frequency:5.1f}Hz, {data_point.phase_shift:5.1f}°"
                            )

                    # Heartbeat
                    if self.mqtt_adapter:
                        self.mqtt_adapter.publish_heartbeat()

                    await asyncio.sleep(0.1)  # 10Hz Update

                logger.info(f"✅ Test #{test_count} abgeschlossen: {quality} {side}")

                if not self.running:
                    break

                # Pause zwischen Tests
                logger.info(f"⏳ Pause {self.endless_pause}s...")
                await asyncio.sleep(self.endless_pause)

        except Exception as e:
            logger.error(f"Fehler in Endlos-Tests: {e}")
        finally:
            logger.info(f"🏁 Endlos-Tests beendet nach {test_count} Tests")

    async def shutdown(self):
        """Beendet Service gracefully"""
        logger.info("Beende EGEA-Simulator Service...")

        # Test stoppen falls aktiv
        if self.simulator and self.simulator.test_active:
            self.simulator.stop_test()

        # MQTT-Adapter trennen
        if self.mqtt_adapter:
            self.mqtt_adapter.disconnect()

        # MQTT-Verbindung trennen
        if self.mqtt_handler:
            self.mqtt_handler.disconnect()

        logger.info("Service beendet")


async def create_service_from_args(args) -> SimulatorService:
    """
    Erstellt Service basierend auf CLI-Argumenten

    Args:
        args: Parsed command line arguments

    Returns:
        Konfigurierter SimulatorService
    """
    # Test-Konfiguration aus Argumenten
    config = TestConfiguration(
        freq_start=args.freq_start,
        freq_end=args.freq_end,
        platform_amplitude=args.amplitude,
        sample_rate=args.sample_rate,
    )

    # Service erstellen mit Test-Modi
    service = SimulatorService(
        config=config,
        endless_mode=args.endless,
        auto_test=args.auto_test,
        test_duration=args.test_duration,
        endless_pause=args.endless_pause,
    )

    # Initiale Dämpfungsqualität setzen
    await service.initialize()
    if service.simulator:
        service.simulator.set_damping_quality(args.damping_quality)

    return service


def setup_logging(log_level: str = "INFO"):
    """Konfiguriert Logging"""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("egea_simulator.log"),
        ],
    )


def parse_arguments():
    """Parst Command-Line-Argumente"""
    parser = argparse.ArgumentParser(
        description="EGEA CAN-Simulator Service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python -m backend.can_simulator_service.main
  python -m backend.can_simulator_service.main --damping-quality excellent
  python -m backend.can_simulator_service.main --auto-test --test-duration 60
  python -m backend.can_simulator_service.main --endless --endless-pause 5
  python -m backend.can_simulator_service.main --freq-start 30 --freq-end 1 --endless
        """,
    )

    # Service-Parameter
    parser.add_argument(
        "--damping-quality",
        choices=["excellent", "good", "acceptable", "poor"],
        default="good",
        help="Simulierte Dämpfungsqualität (default: good)",
    )

    # Test-Parameter
    parser.add_argument(
        "--freq-start",
        type=float,
        default=25.0,
        help="Startfrequenz in Hz (default: 25.0)",
    )

    parser.add_argument(
        "--freq-end", type=float, default=2.0, help="Endfrequenz in Hz (default: 2.0)"
    )

    parser.add_argument(
        "--amplitude",
        type=float,
        default=6.0,
        help="Plattformamplitude in mm (default: 6.0)",
    )

    parser.add_argument(
        "--sample-rate",
        type=float,
        default=100.0,
        help="Sample-Rate in Hz (default: 100.0)",
    )

    # Logging
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log-Level (default: INFO)",
    )

    # Test-Modi
    parser.add_argument(
        "--auto-test",
        action="store_true",
        help="Startet automatisch einen Test beim Start",
    )

    parser.add_argument(
        "--test-duration",
        type=float,
        default=30.0,
        help="Test-Dauer in Sekunden (default: 30.0)",
    )

    parser.add_argument(
        "--endless",
        action="store_true",
        help="Endlos-Modus: Startet kontinuierlich Tests mit wechselnden Qualitäten",
    )

    parser.add_argument(
        "--endless-pause",
        type=float,
        default=3.0,
        help="Pause zwischen endlosen Tests in Sekunden (default: 3.0)",
    )

    return parser.parse_args()


async def main():
    """Hauptfunktion"""
    args = parse_arguments()
    setup_logging(args.log_level)

    logger.info("Starte EGEA CAN-Simulator Service...")
    logger.info(
        f"Konfiguration: damping_quality={args.damping_quality}, "
        f"freq_range={args.freq_start}-{args.freq_end}Hz, "
        f"amplitude={args.amplitude}mm"
    )

    if args.endless:
        logger.info(
            f"🔄 ENDLOS-MODUS aktiviert: {args.test_duration}s Tests, {args.endless_pause}s Pause"
        )
    elif args.auto_test:
        logger.info(f"🚀 AUTO-TEST aktiviert: {args.test_duration}s")
    else:
        logger.info("⏳ Warte auf MQTT-Commands zum Starten von Tests")

    try:
        # Service erstellen und initialisieren
        service = await create_service_from_args(args)

        # Service starten
        await service.run()

    except KeyboardInterrupt:
        logger.info("Service durch Benutzer beendet")
    except Exception as e:
        logger.error(f"Unerwarteter Fehler: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Async Event Loop starten
    asyncio.run(main())
