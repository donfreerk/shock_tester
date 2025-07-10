# suspension_core/protocols/eusama_protocol.py
from .base_protocol import BaseProtocol
import logging

logger = logging.getLogger(__name__)


class EusamaProtocol(BaseProtocol):
    """
    Implementierung des EUSAMA-Protokolls für den Fahrwerkstester.

    Das EUSAMA-Protokoll definiert die CAN-Kommunikation für den Fahrwerkstester
    mit 29-Bit Extended-IDs basierend auf dem ASCII-Code 'EUS' und verschiedenen
    Subcodes für unterschiedliche Nachrichtentypen.
    """

    # Basis-ID (ASCII 'EUS' << 5)
    BASE_ID = 0x08AAAA60

    # Paket-IDs
    RAW_DATA_LEFT_ID = BASE_ID + 0  # Rohdaten der linken Seite
    RAW_DATA_RIGHT_ID = BASE_ID + 1  # Rohdaten der rechten Seite
    MOTOR_STATUS_ID = BASE_ID + 6  # Motorstatus
    TOP_POSITION_ID = BASE_ID + 7  # Oberste Position der Platte

    # Command-IDs (vom externen Gerät zum Schrank)
    MOTOR_CONTROL_ID = BASE_ID + 0x11  # Motor starten/stoppen (0x08AAAA71)
    DISPLAY_CONTROL_ID = BASE_ID + 0x12  # Displaysteuerung
    LAMP_CONTROL_ID = BASE_ID + 0x13  # Lampensteuerung

    # Motor-Masken
    MOTOR_MASK_STOP = 0x00  # Alle Motoren stoppen
    MOTOR_MASK_LEFT = 0x01  # Linker Motor
    MOTOR_MASK_RIGHT = 0x02  # Rechter Motor
    MOTOR_MASK_BOTH = 0x03  # Beide Motoren (nicht empfohlen)

    # Lampen-Masken
    LAMP_MASK_LEFT = 0x01  # Lampe links
    LAMP_MASK_DRIVE_IN = 0x02  # Einfahrlampe (grün)
    LAMP_MASK_RIGHT = 0x04  # Lampe rechts

    # Top-Position-Masken
    TOP_POS_LEFT = 0x01  # Linke Platte in oberster Position
    TOP_POS_RIGHT = 0x02  # Rechte Platte in oberster Position

    def __init__(self, can_interface):
        """
        Initialisiert das EUSAMA-Protokoll mit der angegebenen CAN-Schnittstelle.

        Args:
                can_interface: Eine Instanz der CanInterface-Klasse
        """
        self.can_interface = can_interface
        self.callbacks = {"raw_data": [], "motor_status": [], "top_position": []}

    def send_motor_command(self, side, duration):
        """
        Sendet eine Motorsteuerungsnachricht über die CAN-Schnittstelle.

        Args:
                side: "left", "right", "both" oder "stop"
                duration: Laufzeit des Motors in Sekunden (0-255)

        Returns:
                True bei erfolgreicher Übertragung, sonst False
        """
        cmd = self._create_motor_command(side, duration)
        result = self.can_interface.send_message(
            cmd["arbitration_id"], cmd["data"], cmd["is_extended_id"]
        )
        if result:
            logger.info(f"EUSAMA: Motor-Kommando gesendet - Seite: {side}, Dauer: {duration}s")
        else:
            logger.warning(f"EUSAMA: Fehler beim Senden des Motor-Kommandos - Seite: {side}")
        return result

    def send_lamp_command(self, left=False, drive_in=False, right=False):
        """
        Sendet eine Lampensteuerungsnachricht über die CAN-Schnittstelle.

        Args:
                left: Status der linken Lampe (True=ein, False=aus)
                drive_in: Status der Einfahrlampe (True=ein, False=aus)
                right: Status der rechten Lampe (True=ein, False=aus)

        Returns:
                True bei erfolgreicher Übertragung, sonst False
        """
        cmd = self._create_lamp_command(left, drive_in, right)
        result = self.can_interface.send_message(
            cmd["arbitration_id"], cmd["data"], cmd["is_extended_id"]
        )
        if result:
            logger.info(
                f"EUSAMA: Lampen-Kommando gesendet - Links: {left}, Einfahrt: {drive_in}, Rechts: {right}"
            )
        else:
            logger.warning("EUSAMA: Fehler beim Senden des Lampen-Kommandos")
        return result

    def send_display_command(self, diff_display, left_display, right_display):
        """
        Sendet eine Displaysteuerungsnachricht über die CAN-Schnittstelle.

        Args:
                diff_display: Wert für das Differenz-Display (0-99)
                left_display: Wert für das linke Display (0-999)
                right_display: Wert für das rechte Display (0-999)

        Returns:
                True bei erfolgreicher Übertragung, sonst False
        """
        cmd = self._create_display_command(diff_display, left_display, right_display)
        result = self.can_interface.send_message(
            cmd["arbitration_id"], cmd["data"], cmd["is_extended_id"]
        )
        if result:
            logger.info(
                f"EUSAMA: Display-Kommando gesendet - Diff: {diff_display}, Links: {left_display}, Rechts: {right_display}"
            )
        else:
            logger.warning("EUSAMA: Fehler beim Senden des Display-Kommandos")
        return result

    def register_callbacks(self):
        """
        Registriert Callbacks für die Verarbeitung von EUSAMA-Protokollnachrichten.
        """
        if not self.can_interface:
            logger.error("EUSAMA: Keine CAN-Schnittstelle verfügbar")
            return False

        def on_message(msg):
            """Callback für empfangene CAN-Nachrichten"""
            can_id = msg.arbitration_id

            # Rohdaten der linken Seite
            if can_id == self.RAW_DATA_LEFT_ID:
                data = self._parse_raw_data(msg)
                if data:
                    data["position"] = "front_left"  # Position hinzufügen
                    for callback in self.callbacks["raw_data"]:
                        try:
                            callback(data)
                        except Exception as e:
                            logger.error(f"EUSAMA: Fehler im Callback: {e}")

            # Rohdaten der rechten Seite
            elif can_id == self.RAW_DATA_RIGHT_ID:
                data = self._parse_raw_data(msg)
                if data:
                    data["position"] = "front_right"  # Position hinzufügen
                    for callback in self.callbacks["raw_data"]:
                        try:
                            callback(data)
                        except Exception as e:
                            logger.error(f"EUSAMA: Fehler im Callback: {e}")

            # Motorstatus
            elif can_id == self.MOTOR_STATUS_ID:
                data = self._parse_motor_status(msg)
                for callback in self.callbacks["motor_status"]:
                    try:
                        callback(data)
                    except Exception as e:
                        logger.error(f"EUSAMA: Fehler im Callback: {e}")

            # Oberste Position der Platte
            elif can_id == self.TOP_POSITION_ID:
                data = self._parse_top_position(msg)
                for callback in self.callbacks["top_position"]:
                    try:
                        callback(data)
                    except Exception as e:
                        logger.error(f"EUSAMA: Fehler im Callback: {e}")

        # Callback für alle CAN-Nachrichten registrieren
        self.can_interface.add_message_callback(on_message)
        logger.info("EUSAMA: Callbacks registriert")
        return True

    def add_callback(self, message_type, callback):
        """
        Fügt einen Callback für einen bestimmten Nachrichtentyp hinzu.

        Args:
                message_type: Art der Nachricht ("raw_data", "motor_status", "top_position")
                callback: Callback-Funktion

        Returns:
                True bei erfolgreicher Registrierung, sonst False
        """
        if message_type not in self.callbacks:
            logger.error(f"EUSAMA: Unbekannter Nachrichtentyp: {message_type}")
            return False

        if callback not in self.callbacks[message_type]:
            self.callbacks[message_type].append(callback)
            logger.debug(f"EUSAMA: Callback für {message_type} hinzugefügt")
            return True
        else:
            logger.warning(f"EUSAMA: Callback für {message_type} bereits registriert")
            return False

    def remove_callback(self, message_type, callback):
        """
        Entfernt einen Callback für einen bestimmten Nachrichtentyp.

        Args:
                message_type: Art der Nachricht ("raw_data", "motor_status", "top_position")
                callback: Zu entfernender Callback

        Returns:
                True bei erfolgreicher Entfernung, sonst False
        """
        if message_type not in self.callbacks:
            logger.error(f"EUSAMA: Unbekannter Nachrichtentyp: {message_type}")
            return False

        if callback in self.callbacks[message_type]:
            self.callbacks[message_type].remove(callback)
            logger.debug(f"EUSAMA: Callback für {message_type} entfernt")
            return True
        else:
            logger.warning(f"EUSAMA: Callback für {message_type} nicht gefunden")
            return False

    # Private Methoden zur Erstellung von CAN-Nachrichten
    def _create_motor_command(self, side, duration):
        """
        Erstellt eine Motorsteuerungsnachricht.

        Args:
                side: "left", "right", "both" oder "stop"
                duration: Laufzeit des Motors in Sekunden (0-255)

        Returns:
                Dictionary mit arbitration_id, data und is_extended_id
        """
        # Motor-Maske basierend auf der Seite
        if side == "left":
            motor_mask = self.MOTOR_MASK_LEFT
        elif side == "right":
            motor_mask = self.MOTOR_MASK_RIGHT
        elif side == "both":
            motor_mask = self.MOTOR_MASK_BOTH
        else:  # "stop" oder ungültig
            motor_mask = self.MOTOR_MASK_STOP

        # Dauer begrenzen
        duration = max(0, min(int(duration), 255))

        # Daten erstellen: [Motor-Maske, Dauer, 0, 0, 0, 0, 0, 0]
        data = bytearray([motor_mask, duration, 0, 0, 0, 0, 0, 0])

        return {
            "arbitration_id": self.MOTOR_CONTROL_ID,
            "data": data,
            "is_extended_id": True,
        }

    def _create_lamp_command(self, left=False, drive_in=False, right=False):
        """
        Erstellt eine Lampensteuerungsnachricht.

        Args:
                left: Status der linken Lampe (True=ein, False=aus)
                drive_in: Status der Einfahrlampe (True=ein, False=aus)
                right: Status der rechten Lampe (True=ein, False=aus)

        Returns:
                Dictionary mit arbitration_id, data und is_extended_id
        """
        # Lampen-Maske erstellen
        lamp_mask = 0
        if left:
            lamp_mask |= self.LAMP_MASK_LEFT
        if drive_in:
            lamp_mask |= self.LAMP_MASK_DRIVE_IN
        if right:
            lamp_mask |= self.LAMP_MASK_RIGHT

        # Daten erstellen: [Lampen-Maske, 0, 0, 0, 0, 0, 0, 0]
        data = bytearray([lamp_mask, 0, 0, 0, 0, 0, 0, 0])

        return {
            "arbitration_id": self.LAMP_CONTROL_ID,
            "data": data,
            "is_extended_id": True,
        }

    def _create_display_command(self, diff_display, left_display, right_display):
        """
        Erstellt eine Displaysteuerungsnachricht.

        Args:
                diff_display: Wert für das Differenz-Display (0-99)
                left_display: Wert für das linke Display (0-999)
                right_display: Wert für das rechte Display (0-999)

        Returns:
                Dictionary mit arbitration_id, data und is_extended_id
        """
        # Werte begrenzen
        diff_display = max(0, min(int(diff_display), 99))
        left_display = max(0, min(int(left_display), 999))
        right_display = max(0, min(int(right_display), 999))

        # Daten erstellen: [Diff-Display, 0, Links-Low, Links-High, 0, Rechts-Low, Rechts-High, 0]
        data = bytearray(
            [
                diff_display,
                0,
                left_display & 0xFF,  # Low-Byte
                (left_display >> 8) & 0xFF,  # High-Byte
                0,
                right_display & 0xFF,  # Low-Byte
                (right_display >> 8) & 0xFF,  # High-Byte
                0,
            ]
        )

        return {
            "arbitration_id": self.DISPLAY_CONTROL_ID,
            "data": data,
            "is_extended_id": True,
        }

    # Private Methoden zur Verarbeitung von CAN-Nachrichten
    def _parse_raw_data(self, msg):
        """
        Verarbeitet eine Rohdaten-Nachricht.

        Args:
                msg: CAN-Nachricht

        Returns:
                Dictionary mit den extrahierten Daten
        """
        if len(msg.data) < 8:
            logger.warning("EUSAMA: Ungültige Rohdaten-Nachricht (zu kurz)")
            return None

        # Plattformposition (0-1023)
        platform_position = (msg.data[1] << 8) | msg.data[0]

        # Reifenkraft (0-1023)
        tire_force = (msg.data[3] << 8) | msg.data[2]

        # Frequenz (0-255 Hz)
        frequency = msg.data[4]

        # Phasenverschiebung (0-255 entspricht 0-90°)
        phase_shift = msg.data[5] * (90.0 / 255.0)

        return {
            "platform_position": platform_position,
            "tire_force": tire_force,
            "frequency": frequency,
            "phase_shift": phase_shift,
            "timestamp": msg.timestamp,
        }

    def _parse_motor_status(self, msg):
        """
        Verarbeitet eine Motorstatus-Nachricht.

        Args:
                msg: CAN-Nachricht

        Returns:
                Dictionary mit den extrahierten Daten
        """
        if len(msg.data) < 8:
            logger.warning("EUSAMA: Ungültige Motorstatus-Nachricht (zu kurz)")
            return None

        # Motorstatus (Bit 0: Links, Bit 1: Rechts)
        motor_status = msg.data[0]
        left_running = bool(motor_status & self.MOTOR_MASK_LEFT)
        right_running = bool(motor_status & self.MOTOR_MASK_RIGHT)

        return {"left_running": left_running, "right_running": right_running}

    def _parse_top_position(self, msg):
        """
        Verarbeitet eine Top-Position-Nachricht.

        Args:
                msg: CAN-Nachricht

        Returns:
                Dictionary mit den extrahierten Daten
        """
        if len(msg.data) < 1:
            logger.warning("EUSAMA: Ungültige Top-Position-Nachricht (zu kurz)")
            return None

        # Top-Position-Status (Bit 0: Links, Bit 1: Rechts)
        top_position = msg.data[0]
        left_top = bool(top_position & self.TOP_POS_LEFT)
        right_top = bool(top_position & self.TOP_POS_RIGHT)

        return {"left_top": left_top, "right_top": right_top}