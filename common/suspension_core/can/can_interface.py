"""
CAN-Interface-Modul für die Verbindung mit CAN-Bussen.

Dieses Modul bietet eine einheitliche Schnittstelle für die Verbindung mit dem CAN-Bus,
mit Funktionen wie automatischer Baudratenerkennung, Fehlerbehandlung und Wiederverbindung.
"""

import can
import logging
import time
import threading

logger = logging.getLogger(__name__)


class CanInterface:
    """
    Einheitliche CAN-Schnittstelle mit Baudratenerkennung, Fehlerbehebung und Wiederversuchen.

    Diese Klasse abstrahiert die Details der CAN-Bus-Kommunikation und bietet
    eine robuste Schnittstelle für das Senden und Empfangen von CAN-Nachrichten.

    Attribute:
            channel (str): CAN-Kanal (z.B. "can0")
            baudrates (list): Liste der zu testenden Baudraten
            interface (can.Bus): CAN-Bus-Interface-Objekt
            connected (bool): Verbindungsstatus
            current_baudrate (int): Aktuell verwendete Baudrate
    """

    def __init__(
        self,
        channel="can0",
        auto_detect_baud=True,
        baudrates=None,
        baudrate=None,  # Optional: Einzelne Baudrate
        protocol="asa",
        **kwargs,
    ):
        """
        Initialisiert die CAN-Schnittstelle.

        Args:
            channel (str): CAN-Kanalname (z.B. "can0")
            auto_detect_baud (bool): Automatische Baudratenerkennung aktivieren
            baudrates (list): Liste der zu testenden Baudraten
            baudrate (int): Einzelne Baudrate (Alternative zu baudrates)
            protocol (str): Zu verwendendes Protokoll ("asa" oder "eusama")
            **kwargs: Weitere Parameter für die CAN-Bus-Initialisierung
        """
        self.channel = channel

        # Verwenden einer einzelnen Baudrate, falls angegeben
        if baudrate is not None:
            self.baudrates = [baudrate]
        else:
            # Protokollspezifische Baudraten
            if protocol.lower() == "eusama":  # Korrigiert von "eusema"
                self.baudrates = baudrates or [1000000]  # EUSAMA: 1 Mbits/s
            else:  # ASA
                self.baudrates = baudrates or [
                    250000,
                    125000,
                    9600,
                ]  # ASA: 250 kbit/s, 125 kbit/s, 9600 bit/s

        self.interface = None
        self.connected = False
        self.current_baudrate = None
        self.receive_thread = None
        self.stop_event = threading.Event()
        self.message_callbacks = []
        self.kwargs = kwargs

        if auto_detect_baud:
            self.connect_with_auto_detect()

    def connect_with_auto_detect(self):
        """
        Stellt eine Verbindung mit automatischer Baudratenerkennung her.

        Returns:
                bool: True, wenn die Verbindung erfolgreich war, sonst False
        """
        for baudrate in self.baudrates:
            if self.connect(baudrate):
                return True

        logger.error("Keine funktionierende Baudrate gefunden")
        return False

    def connect(self, baudrate):
        """
        Stellt eine Verbindung mit der angegebenen Baudrate her.

        Args:
                baudrate (int): Zu verwendende Baudrate

        Returns:
                bool: True, wenn die Verbindung erfolgreich war, sonst False
        """
        try:
            logger.info(
                f"Versuche CAN-Verbindung mit {baudrate} bps auf Kanal {self.channel}..."
            )

            # Alte Verbindung schließen, wenn vorhanden
            if self.interface:
                self.shutdown()

                # Sicherstellen, dass der Bus auch bei höheren Baudraten korrekt initialisiert wird
                time.sleep(0.5)

            # CAN-Bus-Interface erstellen
            self.interface = can.interface.Bus(
                channel=self.channel,
                bustype="socketcan",
                bitrate=baudrate,
                **self.kwargs,
            )

            # Verbindung testen
            if self._test_connection():
                self.connected = True
                self.current_baudrate = baudrate
                logger.info(
                    f"CAN-Verbindung erfolgreich hergestellt mit {baudrate} bps"
                )

                # Empfangsthread starten
                self.start_receiver()
                return True
            else:
                logger.warning(
                    f"CAN-Verbindung mit {baudrate} bps hergestellt, aber keine Nachrichten empfangen"
                )
                if self.interface:
                    self.interface.shutdown()
                    self.interface = None
                return False

        except can.CanError as e:
            logger.error(f"Fehler bei der CAN-Verbindung mit {baudrate} bps: {e}")
            if self.interface:
                try:
                    self.interface.shutdown()
                except Exception:
                    pass
                self.interface = None
            return False

    def _test_connection(self, timeout=1):
        """
        Testet die CAN-Verbindung durch Empfangen einer Nachricht.

        Args:
                timeout (float): Timeout in Sekunden

        Returns:
                bool: True, wenn eine Nachricht empfangen wurde, sonst False
        """
        if not self.interface:
            return False

        try:
            # Versuche, eine Nachricht zu empfangen
            msg = self.interface.recv(timeout=timeout)
            if msg:
                logger.debug(f"Testnachricht empfangen: {msg}")
                return True
            else:
                logger.warning("Keine Testnachricht empfangen")
                return False
        except can.CanError as e:
            logger.error(f"Fehler beim Testen der CAN-Verbindung: {e}")
            return False
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Testen der CAN-Verbindung: {e}")
            return False

    def send_message(self, arbitration_id, data, is_extended_id=False, **kwargs):
        """
        Sendet eine CAN-Nachricht.

        Args:
                arbitration_id (int): CAN-ID
                data (bytes): Zu sendende Daten
                is_extended_id (bool): Ob die ID erweitert ist (29 Bit statt 11 Bit)
                **kwargs: Weitere Parameter für die CAN-Nachricht

        Returns:
                bool: True, wenn die Nachricht erfolgreich gesendet wurde, sonst False
        """
        if not self.connected or not self.interface:
            logger.error("Keine CAN-Verbindung hergestellt")
            return False

        try:
            # CAN-Nachricht erstellen
            msg = can.Message(
                arbitration_id=arbitration_id,
                data=data,
                is_extended_id=is_extended_id,
                **kwargs,
            )

            # Nachricht senden
            self.interface.send(msg)
            logger.debug(f"CAN-Nachricht gesendet: {msg}")
            return True
        except can.CanError as e:
            logger.error(f"Fehler beim Senden der CAN-Nachricht: {e}")
            return False
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Senden der CAN-Nachricht: {e}")
            return False

    def recv_message(self, timeout=1.0):
        """
        Empfängt eine CAN-Nachricht.

        Args:
                timeout (float): Timeout in Sekunden

        Returns:
                can.Message: Empfangene Nachricht oder None bei Timeout
        """
        if not self.connected or not self.interface:
            logger.error("Keine CAN-Verbindung hergestellt")
            return None

        try:
            # Nachricht empfangen
            msg = self.interface.recv(timeout=timeout)
            if msg:
                logger.debug(f"CAN-Nachricht empfangen: {msg}")
            return msg
        except can.CanError as e:
            logger.error(f"Fehler beim Empfangen der CAN-Nachricht: {e}")
            return None
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Empfangen der CAN-Nachricht: {e}")
            return None

    def add_message_callback(self, callback):
        """
        Fügt einen Callback für empfangene Nachrichten hinzu.

        Args:
                callback (callable): Callback-Funktion, die bei jeder empfangenen Nachricht aufgerufen wird

        Returns:
                bool: True, wenn der Callback erfolgreich hinzugefügt wurde, sonst False
        """
        if callback not in self.message_callbacks:
            self.message_callbacks.append(callback)
            logger.debug(f"Callback {callback.__name__} hinzugefügt")
            return True
        else:
            logger.warning(f"Callback {callback.__name__} bereits registriert")
            return False

    def remove_message_callback(self, callback):
        """
        Entfernt einen Callback für empfangene Nachrichten.

        Args:
                callback (callable): Zu entfernender Callback

        Returns:
                bool: True, wenn der Callback erfolgreich entfernt wurde, sonst False
        """
        if callback in self.message_callbacks:
            self.message_callbacks.remove(callback)
            logger.debug(f"Callback {callback.__name__} entfernt")
            return True
        else:
            logger.warning(f"Callback {callback.__name__} nicht gefunden")
            return False

    def start_receiver(self):
        """Startet den Empfangsthread."""
        if not self.receive_thread or not self.receive_thread.is_alive():
            self.stop_event.clear()
            self.receive_thread = threading.Thread(target=self._receive_loop)
            self.receive_thread.daemon = True
            self.receive_thread.start()

    def stop_receiver(self):
        """Stoppt den Empfangsthread."""
        if self.receive_thread and self.receive_thread.is_alive():
            self.stop_event.set()
            self.receive_thread.join(timeout=1.0)
            self.receive_thread = None

    def _receive_loop(self):
        """Empfangsschleife für den Empfangsthread."""
        logger.info("CAN-Empfangsthread gestartet")
        while not self.stop_event.is_set() and self.connected:
            try:
                msg = self.recv_message(timeout=0.1)
                if msg:
                    # Alle Callbacks aufrufen
                    for callback in self.message_callbacks:
                        try:
                            callback(msg)
                        except Exception as e:
                            logger.error(f"Fehler im Callback {callback.__name__}: {e}")
            except Exception as e:
                logger.error(f"Fehler in der Empfangsschleife: {e}")
                time.sleep(0.1)  # Kurze Pause bei Fehlern
        logger.info("CAN-Empfangsthread beendet")

    def log_message(self, msg, log_file=None):
        """
        Protokolliert eine CAN-Nachricht.

        Args:
                msg (can.Message): Zu protokollierende Nachricht
                log_file (str): Optionaler Pfad zur Log-Datei
        """
        if not msg:
            return

        # Nachricht formatieren
        timestamp = msg.timestamp
        can_id = f"0x{msg.arbitration_id:X}"
        data_hex = " ".join(f"{b:02X}" for b in msg.data)
        log_entry = f"{timestamp:.6f} {can_id} [{msg.dlc}] {data_hex}"

        # In Datei schreiben, wenn angegeben
        if log_file:
            try:
                with open(log_file, "a") as f:
                    f.write(log_entry + "\n")
            except Exception as e:
                logger.error(f"Fehler beim Schreiben in Log-Datei: {e}")

        # In Logger ausgeben
        logger.debug(f"CAN: {log_entry}")

    def shutdown(self):
        """Beendet die CAN-Verbindung."""
        logger.info("Beende CAN-Verbindung...")
        self.stop_receiver()
        if self.interface:
            try:
                self.interface.shutdown()
                logger.info("CAN-Interface heruntergefahren")
            except Exception as e:
                logger.error(f"Fehler beim Herunterfahren des CAN-Interface: {e}")
            finally:
                self.interface = None
                self.connected = False
                self.current_baudrate = None


def identify_can_ids(can_interface, duration=10, analyze=True):
    """
    Identifiziert aktive CAN-IDs auf dem Bus.

    Args:
            can_interface (CanInterface): CAN-Interface-Objekt
            duration (int): Dauer der Identifikation in Sekunden
            analyze (bool): Ob die Nachrichten analysiert werden sollen

    Returns:
            dict: Dictionary mit CAN-IDs als Schlüssel und Häufigkeit als Werte
    """
    if not can_interface.connected:
        logger.error("Keine CAN-Verbindung hergestellt")
        return {}

    logger.info(f"Identifiziere aktive CAN-IDs für {duration} Sekunden...")
    can_ids = {}
    start_time = time.time()

    while time.time() - start_time < duration:
        msg = can_interface.recv_message(timeout=0.1)
        if msg:
            can_id = msg.arbitration_id
            if can_id in can_ids:
                can_ids[can_id]["count"] += 1
                can_ids[can_id]["data"].append(list(msg.data))
            else:
                can_ids[can_id] = {"count": 1, "data": [list(msg.data)]}

    # Sortieren nach Häufigkeit
    sorted_ids = sorted(can_ids.items(), key=lambda x: x[1]["count"], reverse=True)

    # Ausgabe
    logger.info(f"{len(can_ids)} aktive CAN-IDs identifiziert:")
    for can_id, info in sorted_ids:
        logger.info(f"ID: 0x{can_id:X} - {info['count']} Nachrichten")

    # Analyse
    if analyze and can_ids:
        logger.info("Analysiere Nachrichtenformate...")
        for can_id, info in sorted_ids:
            if info["count"] > 1:
                # Einfache Analyse der Datenstruktur
                data_samples = info["data"]
                data_length = len(data_samples[0])
                
                # Prüfen, ob alle Nachrichten die gleiche Länge haben
                same_length = all(len(data) == data_length for data in data_samples)
                
                # Prüfen, welche Bytes sich ändern
                changing_bytes = []
                if len(data_samples) > 1:
                    for i in range(data_length):
                        values = set(data[i] for data in data_samples)
                        if len(values) > 1:
                            changing_bytes.append(i)
                
                logger.info(
                    f"ID: 0x{can_id:X} - Länge: {data_length} Bytes, "
                    f"Konstante Länge: {same_length}, "
                    f"Sich ändernde Bytes: {changing_bytes}"
                )

    return dict(sorted_ids)