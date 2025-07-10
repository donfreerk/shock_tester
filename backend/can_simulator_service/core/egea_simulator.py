# backend/can_simulator_service/core/egea_simulator.py
"""
EGEA-Simulator Core Domain Logic
Reine Simulationslogik ohne externe Dependencies (MQTT, GUI, etc.)
Folgt hexagonaler Architektur - Domain Layer
"""

import logging
import math
import time
import threading
from dataclasses import dataclass
from typing import Dict, List, Callable, Optional, Any
from enum import Enum

from .config import TestConfiguration

logger = logging.getLogger(__name__)


class DampingQuality(Enum):
    """Dämpfungsqualitäts-Kategorien nach EGEA-Standard"""
    EXCELLENT = "excellent"  # φmin ≥ 45°
    GOOD = "good"           # φmin ≥ 35°
    ACCEPTABLE = "acceptable" # φmin ≥ 25°
    POOR = "poor"           # φmin < 25°


@dataclass
class DampingParameters:
    """Parameter für Dämpfungssimulation"""
    resonance_freq: float      # Resonanzfrequenz in Hz
    min_phase: float          # Minimaler Phasenwinkel in Grad
    damping_ratio: float      # Dämpfungsverhältnis
    rigidity: float           # Reifensteifigkeit in N/mm


@dataclass
class SimulationDataPoint:
    """Ein Datenpunkt der Simulation"""
    timestamp: float
    elapsed: float
    frequency: float
    platform_position: float
    tire_force: float
    phase_shift: float
    dms_values: List[int]  # 4 DMS-Werte [0-1023]


class EGEASimulationEvent:
    """Base class für Simulation Events"""
    pass


@dataclass
class TestStartedEvent(EGEASimulationEvent):
    """Event: Test wurde gestartet"""
    side: str
    duration: float
    timestamp: float


@dataclass
class TestStoppedEvent(EGEASimulationEvent):
    """Event: Test wurde gestoppt"""
    side: str
    timestamp: float


@dataclass
class DataGeneratedEvent(EGEASimulationEvent):
    """Event: Neue Simulationsdaten verfügbar"""
    data_point: SimulationDataPoint
    side: str


@dataclass
class TestCompletedEvent(EGEASimulationEvent):
    """Event: Test vollständig abgeschlossen"""
    side: str
    duration: float
    timestamp: float


class EGEASimulator:
    """
    EGEA-konformer Simulator für Fahrwerksdämpfung
    
    Reine Domain-Logik ohne externe Dependencies.
    Kommuniziert über Events (Observer Pattern).
    """
    
    # Standard-Dämpfungsparameter nach EGEA-Richtlinien
    DEFAULT_DAMPING_PARAMS = {
        DampingQuality.EXCELLENT.value: DampingParameters(
            resonance_freq=12.5,
            min_phase=48.0,
            damping_ratio=0.3,
            rigidity=280.0
        ),
        DampingQuality.GOOD.value: DampingParameters(
            resonance_freq=11.8,
            min_phase=38.0,
            damping_ratio=0.25,
            rigidity=250.0
        ),
        DampingQuality.ACCEPTABLE.value: DampingParameters(
            resonance_freq=10.2,
            min_phase=28.0,
            damping_ratio=0.2,
            rigidity=200.0
        ),
        DampingQuality.POOR.value: DampingParameters(
            resonance_freq=8.5,
            min_phase=18.0,
            damping_ratio=0.15,
            rigidity=150.0
        )
    }
    
    def __init__(self, config: Optional[TestConfiguration] = None):
        """Initialisiert Simulator mit optionaler Konfiguration"""
        self.config = config or TestConfiguration()
        self.damping_params = self.DEFAULT_DAMPING_PARAMS.copy()
        
        # Zustandsvariablen
        self.current_damping_quality = DampingQuality.GOOD.value
        self.test_active = False
        self.current_side = ""
        self.test_duration = 0.0
        self.test_start_time = 0.0
        self.simulation_time = 0.0
        
        # Event-Handler (Observer Pattern)
        self._event_handlers: List[Callable[[EGEASimulationEvent], None]] = []
        
        # Thread-Synchronisation
        self._lock = threading.Lock()
        
    def subscribe_to_events(self, handler: Callable[[EGEASimulationEvent], None]):
        """Registriert Event-Handler"""
        with self._lock:
            if handler not in self._event_handlers:
                self._event_handlers.append(handler)
                logger.debug(f"Event-Handler registriert: {handler}")
    
    def unsubscribe_from_events(self, handler: Callable[[EGEASimulationEvent], None]):
        """Entfernt Event-Handler"""
        with self._lock:
            if handler in self._event_handlers:
                self._event_handlers.remove(handler)
                logger.debug(f"Event-Handler entfernt: {handler}")
    
    def _emit_event(self, event: EGEASimulationEvent):
        """Sendet Event an alle registrierten Handler"""
        with self._lock:
            handlers = self._event_handlers.copy()
        
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Fehler in Event-Handler {handler}: {e}")
    
    def set_damping_quality(self, quality: str):
        """
        Setzt Dämpfungsqualität für Simulation
        
        Args:
            quality: Dämpfungsqualität aus DampingQuality enum
        """
        if quality in self.damping_params:
            self.current_damping_quality = quality
            logger.info(f"Dämpfungsqualität gesetzt: {quality}")
        else:
            available = list(self.damping_params.keys())
            raise ValueError(f"Unbekannte Dämpfungsqualität: {quality}. Verfügbar: {available}")
    
    def add_custom_damping_params(self, quality: str, params: DampingParameters):
        """Fügt benutzerdefinierte Dämpfungsparameter hinzu"""
        self.damping_params[quality] = params
        logger.info(f"Benutzerdefinierte Dämpfungsparameter hinzugefügt: {quality}")
    
    def start_test(self, side: str, duration: float):
        """
        Startet EGEA-konformen Test
        
        Args:
            side: Fahrzeugseite ("left" oder "right")
            duration: Testdauer in Sekunden
        """
        if side not in ["left", "right"]:
            raise ValueError(f"Ungültige Fahrzeugseite: {side}")
        
        if duration <= 0:
            raise ValueError(f"Testdauer muss positiv sein: {duration}")
        
        # Vorherigen Test stoppen falls aktiv
        if self.test_active:
            self.stop_test()
        
        # Test-Parameter setzen
        self.current_side = side
        self.test_duration = duration
        self.test_start_time = time.time()
        self.simulation_time = 0.0
        self.test_active = True
        
        # Event senden
        event = TestStartedEvent(
            side=side,
            duration=duration,
            timestamp=self.test_start_time
        )
        self._emit_event(event)
        
        logger.info(f"EGEA-Test gestartet: {side}, {duration:.1f}s")
    
    def stop_test(self):
        """Stoppt aktuell laufenden Test"""
        if self.test_active:
            self.test_active = False
            
            # Event senden
            event = TestStoppedEvent(
                side=self.current_side,
                timestamp=time.time()
            )
            self._emit_event(event)
            
            logger.info(f"EGEA-Test gestoppt: {self.current_side}")
    
    def generate_data_point(self) -> Optional[SimulationDataPoint]:
        """
        Generiert einen EGEA-konformen Simulationsdatenpunkt
        
        Returns:
            SimulationDataPoint oder None wenn Test nicht aktiv
        """
        if not self.test_active:
            return None
        
        current_time = time.time()
        elapsed = current_time - self.test_start_time
        
        # Test beenden wenn Dauer erreicht
        if elapsed >= self.test_duration:
            self._complete_test()
            return None
        
        # Physikalische Berechnung der Simulationswerte
        data_point = self._calculate_physics(current_time, elapsed)
        
        # Event senden
        event = DataGeneratedEvent(
            data_point=data_point,
            side=self.current_side
        )
        self._emit_event(event)
        
        return data_point
    
    def _complete_test(self):
        """Komplettiert Test und sendet Completion-Event"""
        if self.test_active:
            side = self.current_side
            duration = self.test_duration
            
            self.test_active = False
            
            # Completion Event senden
            event = TestCompletedEvent(
                side=side,
                duration=duration,
                timestamp=time.time()
            )
            self._emit_event(event)
            
            logger.info(f"EGEA-Test abgeschlossen: {side}, {duration:.1f}s")
    
    def _calculate_physics(self, current_time: float, elapsed: float) -> SimulationDataPoint:
        """
        Berechnet physikalisch realistische Simulationswerte
        
        Implementiert EGEA-konforme Phasenverschiebungsberechnung
        """
        # Aktuelle Frequenz (linearer Sweep)
        progress = elapsed / self.test_duration
        frequency = self.config.freq_start - progress * (self.config.freq_start - self.config.freq_end)
        
        # Dämpfungsparameter abrufen
        damping = self.damping_params[self.current_damping_quality]
        
        # Phasenverschiebung berechnen (EGEA-Modell)
        freq_factor = abs(frequency - damping.resonance_freq) / 10.0
        phase_shift = damping.min_phase + 15.0 * math.exp(-2 * freq_factor)
        phase_rad = math.radians(phase_shift)
        
        # Plattformposition (Sinuswelle)
        platform_pos = self.config.platform_amplitude * math.sin(
            2 * math.pi * frequency * elapsed
        )
        
        # Reifenkraft mit Phasenverschiebung
        static_weight = 512  # AD-Mittelwert (0-1023 Bereich)
        force_amplitude = 100 * (1.0 + 0.5 * math.exp(-freq_factor))
        tire_force = static_weight + force_amplitude * math.sin(
            2 * math.pi * frequency * elapsed - phase_rad
        )
        
        # DMS-Werte generieren (4 Dehnungsmessstreifen)
        dms_values = self._generate_dms_values(platform_pos, tire_force, static_weight)
        
        return SimulationDataPoint(
            timestamp=current_time,
            elapsed=elapsed,
            frequency=frequency,
            platform_position=platform_pos,
            tire_force=tire_force,
            phase_shift=phase_shift,
            dms_values=dms_values
        )
    
    def _generate_dms_values(self, platform_pos: float, tire_force: float, static_weight: float) -> List[int]:
        """
        Generiert realistische DMS-Werte (0-1023 Bereich)
        
        Args:
            platform_pos: Plattformposition in mm
            tire_force: Reifenkraft (normiert)
            static_weight: Statisches Gewicht
            
        Returns:
            Liste von 4 DMS-Werten [0-1023]
        """
        # DMS1 & DMS2: Plattform-Sensoren (leicht unterschiedlich kalibriert)
        dms1 = int(max(0, min(1023, static_weight + platform_pos * 20)))
        dms2 = int(max(0, min(1023, static_weight + platform_pos * 18)))
        
        # DMS3 & DMS4: Reifen-Kraftsensoren
        dms3 = int(max(0, min(1023, tire_force)))
        dms4 = int(max(0, min(1023, tire_force * 0.95)))  # Leichte Asymmetrie
        
        return [dms1, dms2, dms3, dms4]
    
    def get_current_status(self) -> Dict[str, Any]:
        """
        Gibt aktuellen Simulator-Status zurück
        
        Returns:
            Dictionary mit Statusinformationen
        """
        return {
            "test_active": self.test_active,
            "current_side": self.current_side,
            "test_duration": self.test_duration,
            "elapsed_time": time.time() - self.test_start_time if self.test_active else 0.0,
            "damping_quality": self.current_damping_quality,
            "config": {
                "freq_start": self.config.freq_start,
                "freq_end": self.config.freq_end,
                "platform_amplitude": self.config.platform_amplitude,
                "sample_rate": self.config.sample_rate
            }
        }