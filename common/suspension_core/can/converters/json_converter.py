import time
from typing import Any, Dict, Optional, Tuple

import can


class CanMessageConverter:
    """
    Konvertiert zwischen CAN-Nachrichten und JSON-Formaten.

    Diese Klasse ersetzt die älteren getrennten Switch-Klassen mit einer
    einheitlichen API für die Konvertierung in beide Richtungen.
    """

    def __init__(self) -> None:
        # Hier könnten interne Mappings oder Lookup-Tabellen initialisiert werden
        self._message_handlers = self._init_message_handlers()

    def _init_message_handlers(self):
        """Initialisiert die Handler-Mappings für verschiedene CAN-IDs"""
        # Rückgabe eines Dictionaries mit CAN-IDs als Schlüssel und Handler-Funktionen als Werte
        return {
            0x8290982: self._handle_ahl02_pressure,
            # 0x8290983: self._handle_ahl03_pressure,
            # weitere Handler hier
        }

    def can_to_json(self, can_message: can.Message) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Konvertiert eine CAN-Nachricht in ein JSON-Format"""
        # CAN-ID abrufen
        can_id = can_message.arbitration_id

        # Passenden Handler suchen
        handler = self._message_handlers.get(can_id)
        if handler:
            return handler(can_message.data)

        # Fallback für unbekannte IDs
        return self._handle_unknown_message(can_message)

    def json_to_can(self, topic: str, json_data: Dict[str, Any]) -> Optional[can.Message]:
        """Konvertiert JSON-Daten in eine CAN-Nachricht"""
        # Implementierung der Konvertierungslogik
        # ...

    # Handler-Methoden für spezifische CAN-IDs
    def _handle_ahl02_pressure(self, data: bytes) -> Tuple[str, Dict[str, Any]]:
        """Handler für AHL02 Pressure-Nachrichten

        Konvertiert die Binärdaten einer AHL02 Pressure-Nachricht in ein strukturiertes
        JSON-Format mit entsprechenden Druckwerten.

        Args:
            data: Die Binärdaten der CAN-Nachricht

        Returns:
            Ein Tupel aus Topic-String und einem Dictionary mit den konvertierten Daten
        """
        # Überprüfen, ob genügend Daten vorhanden sind
        if len(data) < 8:
            return "error/ahl02", {"error": "Unzureichende Datenlänge"}

        # Druckwerte extrahieren (Beispiel für 2-Byte-Werte mit little-endian)
        pressure_front_left = int.from_bytes(data[0:2], byteorder="little") / 100.0  # kPa
        pressure_front_right = int.from_bytes(data[2:4], byteorder="little") / 100.0  # kPa
        pressure_rear_left = int.from_bytes(data[4:6], byteorder="little") / 100.0  # kPa
        pressure_rear_right = int.from_bytes(data[6:8], byteorder="little") / 100.0  # kPa

        # JSON-Dictionary erstellen
        result = {
            "pressures": {
                "front_left": pressure_front_left,
                "front_right": pressure_front_right,
                "rear_left": pressure_rear_left,
                "rear_right": pressure_rear_right,
            },
            "unit": "kPa",
            "timestamp": time.time(),
        }

        return "sensors/pressure", result

    def _handle_unknown_message(self, can_message: can.Message) -> Tuple[str, Dict[str, Any]]:
        """Generischer Handler für unbekannte CAN-IDs"""
        return "unknown", {
            "can_id": hex(can_message.arbitration_id),
            "data": list(can_message.data),
            "timestamp": can_message.timestamp,
        }