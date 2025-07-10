import logging
import sys

from suspension_core.config.manager import ConfigManager

logger = logging.getLogger(__name__)


def create_can_interface(config=None, simulation_type="low_level", simulation_profile=None):
    """
    Factory-Methode zur Erstellung des passenden CAN-Interfaces
    basierend auf der Konfiguration.

    Args:
        config: Optionales ConfigManager-Objekt
        simulation_type: Art der Simulation, wenn Simulator verwendet wird
                        "low_level" = Rohe CAN-Frames
                        "high_level" = Interpretierte Daten
                        "hybrid" = Beides gleichzeitig
        simulation_profile: Optionales Simulationsprofil ("eusama" oder "asa")
                            Überschreibt die Konfiguration, wenn angegeben

    Returns:
        Ein CAN-Interface-Objekt, das die notwendigen Methoden bereitstellt
    """
    if config is None:
        config = ConfigManager()

    use_simulator = config.get(["can", "use_simulator"], True)  # Immer True für den Simulator

    # Auf Windows automatisch den Simulator verwenden
    if sys.platform == "win32":
        use_simulator = True
        logger.info("Windows-System erkannt - verwende automatisch CAN-Simulator")

    # Echtes CAN-Interface verwenden, wenn verfügbar und konfiguriert
    if not use_simulator:
        try:
            from suspension_core.can.can_interface import CanInterface

            channel = config.get(["can", "interface"], "can0")
            baudrate = config.get(["can", "baudrate"], 1000000)
            protocol = config.get(["can", "protocol"], "eusama")

            logger.info(f"Verwende echtes CAN-Interface auf Kanal {channel}")
            return CanInterface(
                channel=channel,
                baudrate=baudrate,
                protocol=protocol,
                auto_detect_baud=config.get(["can", "auto_detect_baud"], True),
            )
        except Exception as e:
            logger.error(f"Fehler beim Initialisieren des echten CAN-Interface: {e}")
            logger.warning("Falle zurück auf Simulator")
            use_simulator = True

    # Spezielle Simulationstypen direkt verarbeiten
    if use_simulator:
        # Simulationsprofil festlegen - wenn explizit angegeben, sonst aus Konfiguration
        profile = simulation_profile or config.get(["can", "simulation_profile"], "eusama")

        if simulation_type == "hybrid":
            # Hybrid-Simulator für gleichzeitige Low-Level- und High-Level-Simulation
            try:
                from suspension_core.can.hybrid_simulator import (
                    HybridSimulator,
                )

                logger.info("Verwende Hybrid-Simulator mit Low-Level- und High-Level-Simulation")
                simulator = HybridSimulator()

                # Zusätzliche Konfigurationen aus den Einstellungen übernehmen
                if config:
                    # Simulationsprofil setzen (EUSAMA oder ASA)
                    simulator.set_simulation_profile(profile)

                    # Low-Level-Generierung ein-/ausschalten
                    generate_low_level = config.get(["simulator", "generate_low_level"], True)
                    simulator.set_generate_low_level(generate_low_level)

                    # Dämpfungsqualität setzen
                    damping_quality = config.get(["simulator", "damping_quality"], "good")
                    simulator.set_damping_quality(damping_quality)

                return simulator
            except ImportError as e:
                logger.error(f"Hybrid-Simulator konnte nicht importiert werden: {e}")
                logger.warning("Falle zurück auf High-Level-Simulator")
                simulation_type = "high_level"  # Fallback

        elif simulation_type == "high_level":
            # High-Level-Simulator für interpretierte Daten
            try:
                from can_simulator_app.core.high_level_simulator import (
                    DataSimulator,
                )

                logger.info("Verwende High-Level-Simulator mit interpretierten Daten")
                simulator = DataSimulator()

                # Zusätzliche Konfigurationen aus den Einstellungen übernehmen
                if config:
                    # Dämpfungsqualität setzen
                    damping_quality = config.get(["simulator", "damping_quality"], "good")
                    simulator.set_damping_quality(damping_quality)

                    # Testmethode setzen
                    test_method = config.get(["simulator", "test_method"], "phase_shift")
                    simulator.set_test_method(test_method)

                return simulator
            except ImportError as e:
                logger.error(f"High-Level-Simulator konnte nicht importiert werden: {e}")
                logger.warning("Falle zurück auf Low-Level-Simulator")
                # Weitermachen mit Low-Level-Simulator als Fallback

        # Low-Level-Simulator (Standard)
        try:
            # Versuche das interne can_simulator-Modul zu importieren
            from suspension_core.can.simulator import SimulatedCanInterface

            logger.info(f"Verwende internes can_simulator-Modul mit Profil {profile}")
            return SimulatedCanInterface(
                simulation_profile=profile,
                auto_generate=True,
                message_interval=0.001,  # 1000 Hz für realistische Simulation
            )
        except ImportError:
            # Fallback: Versuche Windows-Version zu verwenden
            try:
                # Für Windows-Systeme
                if sys.platform == "win32":
                    from can_simulator_app.core.windows_adapter import (
                        WindowsCanInterface,
                    )

                    logger.info(f"Verwende Windows CAN-Simulator mit Profil {profile}")
                    return WindowsCanInterface(simulation_profile=profile, message_interval=0.001)
                # Für andere Systeme
                from can_simulator_app.core.simulator import (
                    SimulatedCanInterface,
                )

                logger.info(f"Verwende internen CAN-Simulator mit Profil {profile}")
                return SimulatedCanInterface(
                    simulation_profile=profile,
                    auto_generate=True,
                    message_interval=0.001,
                )
            except ImportError as e:
                logger.error(f"Fehler beim Import des CAN-Simulators: {e}")
                raise

    # Sollte nie erreicht werden, da wir entweder ein echtes Interface oder einen Simulator zurückgeben
    logger.error("Konnte kein CAN-Interface erstellen")
    raise RuntimeError("Konnte kein CAN-Interface erstellen")