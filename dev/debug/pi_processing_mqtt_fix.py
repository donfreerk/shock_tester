#!/usr/bin/env python3
"""
Pi Processing Service - MQTT Topic Fix
Behebt das Problem mit fehlenden Datenpunkten durch korrekte Topic-Subscriptions

WICHTIGE DEBUG-DATEI: Zeigt MQTT-Topic-Probleme und Lösungsansätze auf
"""

import asyncio
import json
import logging
import signal
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
import numpy as np

# Füge das Project Root zum Python-Pfad hinzu (angepasst für dev/debug/)
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "common"))

try:
    from suspension_core.mqtt.handler import MqttHandler
    from suspension_core.config.manager import ConfigManager
except ImportError as e:
    print(f"Import-Fehler: {e}")
    print("Dieses Script ist für Debugging-Zwecke und benötigt die suspension_core Library")
    sys.exit(1)

logger = logging.getLogger(__name__)


class PiProcessingService:
    """
    Verbesserte Pi Processing Service mit korrigierten MQTT-Topics
    
    CRITICAL FIX: Abonniert die richtigen Topics für Datensammlung
    
    DEBUG-ERKENNTNISSE:
    1. Hardware Bridge sendet auf "suspension/status" statt "suspension/measurements/processed"
    2. Test-Status wird über "suspension/test/status" gesendet
    3. Topics müssen explizit abonniert werden - Auto-Discovery funktioniert nicht
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialisiert den Pi Processing Service"""
        # Konfiguration laden
        self.config = ConfigManager(config_path)
        
        # MQTT-Handler initialisieren
        self.mqtt_handler = MqttHandler(
            client_id=f"pi_processing_debug_{int(time.time())}",
            host=self.config.get(["mqtt", "broker"], "localhost"),
            port=self.config.get(["mqtt", "port"], 1883),
            app_type="processor"
        )
        
        # Datensammlung für aktive Tests
        self.active_tests: Dict[str, Dict[str, Any]] = {}
        self.test_timeouts: Dict[str, float] = {}
        self.running = False
        
        # DEBUG: Statistics für Debugging
        self.received_messages = 0
        self.processed_tests = 0
        self.topic_message_counts = {}  # Zähle Messages pro Topic
        
        logger.info("🔧 DEBUG Pi Processing Service initialisiert")

    async def _setup_mqtt_subscriptions(self):
        """
        CRITICAL FIX: Richtet die korrekten MQTT-Topic-Subscriptions ein
        
        PROBLEM IDENTIFIZIERT: Der Service hat die falschen Topics abonniert!
        
        ORIGINAL (FALSCH):
        - suspension/measurements/processed (sendet niemand)
        
        KORREKTUR (RICHTIG):
        - suspension/status (Hardware Bridge sendet hier)
        - suspension/test/status (für Test-Start/Stop)
        """
        try:
            logger.info("🔧 DEBUG: Richte korrigierte MQTT-Subscriptions ein...")
            
            # 1. HAUPT-KORREKTUR: Hardware Bridge Topic
            self.mqtt_handler.subscribe("suspension/status", self._handle_measurement_data_sync)
            logger.info("   ✅ KORREKTUR: Abonniert 'suspension/status' (Hardware Bridge)")
            
            # 2. Test-Steuerung
            self.mqtt_handler.subscribe("suspension/test/status", self._handle_test_status_sync)
            logger.info("   ✅ Abonniert 'suspension/test/status' (Test-Steuerung)")
            
            # 3. FALLBACK: Behalte alte Topics für Kompatibilität
            fallback_topics = [
                "suspension/measurements/processed",
                "suspension/processing/raw_data",
                "suspension/hardware/sensor"
            ]
            
            for topic in fallback_topics:
                self.mqtt_handler.subscribe(topic, self._handle_measurement_data_sync)
                logger.info(f"   📱 Fallback: Abonniert '{topic}'")
            
            # 4. Service-Commands
            self.mqtt_handler.subscribe("suspension/processing/command", self._handle_processing_command_sync)
            
            # 5. Test-Completion Events
            self.mqtt_handler.subscribe("suspension/test/completed", self._handle_test_completed_sync)
            
            # 6. DEBUG: Wildcard-Subscription für Analyse
            self.mqtt_handler.subscribe("suspension/#", self._handle_debug_message_sync)
            logger.info("   🔍 DEBUG: Abonniert 'suspension/#' für Vollständige Nachrichtenanalyse")
            
            logger.info("🔧 DEBUG: MQTT-Subscriptions KORRIGIERT eingerichtet")
            
        except Exception as e:
            logger.error(f"Fehler beim Einrichten der MQTT-Subscriptions: {e}")

    def _handle_debug_message_sync(self, topic: str, message: str):
        """
        DEBUG HANDLER: Analysiert alle empfangenen MQTT-Nachrichten
        """
        try:
            # Zähle Messages pro Topic
            if topic not in self.topic_message_counts:
                self.topic_message_counts[topic] = 0
            self.topic_message_counts[topic] += 1
            
            # Alle 100 Messages: Debug-Report
            total_messages = sum(self.topic_message_counts.values())
            if total_messages % 100 == 0:
                logger.info("🔍 DEBUG REPORT - Message-Verteilung nach Topics:")
                sorted_topics = sorted(self.topic_message_counts.items(), 
                                     key=lambda x: x[1], reverse=True)
                for topic_name, count in sorted_topics:
                    logger.info(f"   {count:4d} Messages: {topic_name}")
                logger.info(f"   GESAMT: {total_messages} Messages empfangen")
            
            # Bei wichtigen Topics: Detaillierte Analyse
            if topic in ["suspension/status", "suspension/test/status"]:
                try:
                    data = json.loads(message) if isinstance(message, str) else message
                    logger.debug(f"🔍 WICHTIG {topic}: Keys = {list(data.keys()) if isinstance(data, dict) else type(data)}")
                except:
                    logger.debug(f"🔍 WICHTIG {topic}: Raw message (nicht JSON)")
            
        except Exception as e:
            logger.error(f"Fehler im Debug-Handler: {e}")

    def _handle_measurement_data_sync(self, topic: str, message: str):
        """
        KORRIGIERTE IMPLEMENTATION: Handler für Messdaten von allen relevanten Topics
        """
        try:
            data = json.loads(message) if isinstance(message, str) else message
            
            # DEBUG-Logging für wichtige Topics
            if topic == "suspension/status":
                self.received_messages += 1
                if self.received_messages <= 10 or self.received_messages % 50 == 0:
                    logger.info(f"📨 KORREKTUR WIRKT: Message #{self.received_messages} von 'suspension/status'")
                    if isinstance(data, dict):
                        logger.debug(f"   Data keys: {list(data.keys())}")
            
            # In Event-Loop einreihen
            asyncio.create_task(self._handle_measurement_data(topic, data))
            
        except Exception as e:
            logger.error(f"Fehler beim Verarbeiten der Messdaten von {topic}: {e}")

    async def _handle_measurement_data(self, topic: str, data: Dict[str, Any]):
        """
        VERBESSERTE Messdaten-Verarbeitung mit Auto-Test-Detection
        """
        try:
            # VERBESSERUNG: Auto-Detection für Tests ohne explizite Test-ID
            timestamp = data.get("timestamp", time.time())
            
            # Finde oder erstelle passenden Test
            active_test_id = self._find_or_create_active_test(data, timestamp)
            
            if active_test_id:
                # Füge Datenpunkt hinzu
                self.active_tests[active_test_id]["data_points"].append({
                    "timestamp": timestamp,
                    "topic": topic,
                    "data": data
                })
                
                # DEBUG: Progress-Tracking
                data_count = len(self.active_tests[active_test_id]["data_points"])
                if data_count in [1, 10, 50, 100] or data_count % 100 == 0:
                    logger.info(f"🔍 DEBUG: Test {active_test_id} hat jetzt {data_count} Datenpunkte (von {topic})")
                    
            else:
                # DEBUG: Unerwartete Daten
                logger.debug(f"🔍 DEBUG: Datenpunkt ohne aktiven Test empfangen von {topic}")
                
        except Exception as e:
            logger.error(f"Fehler beim Verarbeiten der Messdaten: {e}")

    def _find_or_create_active_test(self, data: Dict[str, Any], timestamp: float) -> Optional[str]:
        """
        AUTO-DETECTION: Findet oder erstellt einen passenden Test für empfangene Daten
        """
        # 1. Existierende Test-ID in den Daten?
        if "test_id" in data and data["test_id"] in self.active_tests:
            return data["test_id"]
        
        # 2. Position-basierte Zuordnung
        position = data.get("position") or data.get("wheel_position")
        if position:
            # Suche Test mit passender Position
            for test_id, test_data in self.active_tests.items():
                if test_data.get("position") == position:
                    # Prüfe ob Zeitstempel plausibel ist
                    start_time = test_data.get("start_time", 0)
                    if timestamp > start_time and (timestamp - start_time) < 300:  # Max 5 Minuten
                        return test_id
        
        # 3. Zeitbasierte Zuordnung (neuester Test)
        if self.active_tests:
            latest_test_id = max(self.active_tests.keys(), 
                                key=lambda x: self.active_tests[x].get("start_time", 0))
            latest_start = self.active_tests[latest_test_id].get("start_time", 0)
            
            # Nur zuordnen wenn Zeitstempel plausibel
            if timestamp > latest_start and (timestamp - latest_start) < 300:  # Max 5 Minuten
                return latest_test_id
        
        # 4. AUTO-CREATE: Erstelle neuen Test wenn Daten "testähnlich" aussehen
        if self._looks_like_test_data(data):
            auto_test_id = f"auto_test_{int(timestamp)}_{position or 'unknown'}"
            logger.info(f"🔧 AUTO-CREATE: Erstelle automatischen Test {auto_test_id}")
            
            self.active_tests[auto_test_id] = {
                "test_id": auto_test_id,
                "position": position or "unknown",
                "start_time": timestamp,
                "data_points": [],
                "metadata": {"auto_created": True, "first_data": data},
                "auto_timeout": timestamp + 120  # 2 Minuten Auto-Timeout
            }
            
            return auto_test_id
        
        return None

    def _looks_like_test_data(self, data: Dict[str, Any]) -> bool:
        """
        Heuristik: Prüft ob empfangene Daten wie Testdaten aussehen
        """
        # Typische Test-Daten-Indikatoren
        test_indicators = [
            "force", "weight", "position", "measurement",
            "sensor", "value", "amplitude", "frequency"
        ]
        
        if isinstance(data, dict):
            data_keys = set(str(k).lower() for k in data.keys())
            
            # Wenn mindestens ein Test-Indikator vorhanden
            for indicator in test_indicators:
                if any(indicator in key for key in data_keys):
                    return True
        
        return False

    # [Weitere Methoden gekürzt - vollständige Version im backup/]
    
    async def start(self):
        """Startet den DEBUG Processing Service"""
        try:
            logger.info("🔧 Starte DEBUG Pi Processing Service...")
            
            # MQTT-Verbindung herstellen
            if not await self._connect_mqtt():
                logger.error("MQTT-Verbindung fehlgeschlagen")
                return False
            
            # KORRIGIERTE Topic-Subscriptions
            await self._setup_mqtt_subscriptions()
            
            self.running = True
            
            # Status senden
            await self._send_status("online", "debug_ready")
            
            logger.info("🔧 DEBUG Pi Processing Service gestartet - analysiert MQTT-Traffic")
            
            # Vereinfachte Service-Loops für Debugging
            await asyncio.gather(
                self._debug_processing_loop(),
                self._mqtt_message_loop(),
                self._debug_heartbeat_loop()
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Fehler beim Starten des DEBUG Services: {e}")
            return False

    async def _debug_processing_loop(self):
        """DEBUG Processing-Loop mit erweiterten Analysen"""
        logger.info("🔧 DEBUG Processing-Loop gestartet")
        
        while self.running:
            try:
                # Alle 30 Sekunden: Status-Report
                if int(time.time()) % 30 == 0:
                    await self._send_debug_status_report()
                
                await asyncio.sleep(1.0)
                
            except Exception as e:
                logger.error(f"Fehler in DEBUG Processing-Loop: {e}")

    async def _debug_heartbeat_loop(self):
        """DEBUG Heartbeat mit erweiterten Informationen"""
        while self.running:
            try:
                await self._send_debug_heartbeat()
                await asyncio.sleep(15.0)  # Häufigerer Heartbeat für Debugging
            except Exception as e:
                logger.error(f"Fehler in DEBUG Heartbeat-Loop: {e}")

    async def _send_debug_status_report(self):
        """Sendet detaillierten Debug-Status-Report"""
        report = {
            "service": "pi_processing_debug",
            "timestamp": time.time(),
            "received_messages": self.received_messages,
            "active_tests": len(self.active_tests),
            "processed_tests": self.processed_tests,
            "topic_message_counts": self.topic_message_counts,
            "test_details": {
                test_id: {
                    "data_points": len(test_data["data_points"]),
                    "start_time": test_data["start_time"],
                    "position": test_data["position"]
                }
                for test_id, test_data in self.active_tests.items()
            }
        }
        
        await self.mqtt_handler.publish_async("suspension/debug/processing_report", report)
        logger.info(f"🔧 DEBUG-Report gesendet: {self.received_messages} Messages, "
                   f"{len(self.active_tests)} aktive Tests")

    async def _send_debug_heartbeat(self):
        """Sendet Debug-Heartbeat"""
        heartbeat = {
            "service": "pi_processing_debug",
            "status": "debug_running",
            "timestamp": time.time(),
            "uptime": time.time() - (hasattr(self, 'start_time') and self.start_time or time.time()),
            "message_rate": self.received_messages,
            "active_tests": list(self.active_tests.keys()),
            "top_topics": dict(sorted(self.topic_message_counts.items(), 
                                    key=lambda x: x[1], reverse=True)[:5])
        }
        
        await self.mqtt_handler.publish_async("suspension/debug/heartbeat", heartbeat)

    # [Weitere Standard-Methoden wie _connect_mqtt, stop, etc. hier]
    
    async def _connect_mqtt(self) -> bool:
        """Stellt MQTT-Verbindung her"""
        try:
            success = self.mqtt_handler.connect()
            if success:
                logger.info("🔧 DEBUG: MQTT-Verbindung hergestellt")
                return True
            else:
                logger.error("🔧 DEBUG: MQTT-Verbindung fehlgeschlagen")
                return False
        except Exception as e:
            logger.error(f"🔧 DEBUG: MQTT-Verbindungsfehler: {e}")
            return False


# DEBUG Main-Funktion
async def main():
    """DEBUG Hauptfunktion"""
    import argparse
    
    parser = argparse.ArgumentParser(description="DEBUG Pi Processing Service - MQTT Topic Fix")
    parser.add_argument("--config", help="Pfad zur Konfigurationsdatei")
    parser.add_argument("--broker", default="localhost", help="MQTT-Broker-Adresse")
    parser.add_argument("--debug", action="store_true", default=True, help="Debug-Modus (standardmäßig aktiviert)")
    
    args = parser.parse_args()
    
    # Debug-Logging aktivieren
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    logger.info("🔧 ===== STARTING DEBUG PI PROCESSING SERVICE =====")
    logger.info("🔧 Dieser Service analysiert MQTT-Topic-Probleme")
    logger.info("🔧 Publiziert Debug-Berichte auf suspension/debug/*")
    
    # Service erstellen
    service = PiProcessingService(args.config)
    service.start_time = time.time()
    
    try:
        # Service starten
        success = await service.start()
        if not success:
            logger.error("🔧 DEBUG: Service konnte nicht gestartet werden")
            return 1
        
        logger.info("🔧 DEBUG: Service läuft - analysiert MQTT-Topics...")
        
        # Haupt-Loop
        while service.running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("🔧 DEBUG: Beende Service...")
    except Exception as e:
        logger.error(f"🔧 DEBUG: Unerwarteter Fehler: {e}")
        return 1
    finally:
        if hasattr(service, 'stop'):
            await service.stop()
    
    logger.info("🔧 ===== DEBUG PI PROCESSING SERVICE BEENDET =====")
    return 0


if __name__ == "__main__":
    print("🔧 DEBUG PI PROCESSING SERVICE - MQTT TOPIC FIX")
    print("🔧 Analysiert MQTT-Nachrichten und identifiziert Topic-Probleme")
    print("🔧 Für Produktions-Service verwenden Sie: backend/pi_processing_service/main.py")
    sys.exit(asyncio.run(main()))
