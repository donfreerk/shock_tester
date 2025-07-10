# suspension_core/protocols/base_protocol.py
from abc import ABC, abstractmethod


class BaseProtocol(ABC):
    """
    Abstrakte Basisklasse für CAN-Protokollimplementierungen.

    Diese Klasse definiert die gemeinsame Schnittstelle, die alle
    Protokollimplementierungen bereitstellen müssen.
    """

    @abstractmethod
    def send_motor_command(self, side, duration):
        """
        Sendet eine Motorsteuerungsnachricht.

        Args:
                side: Motorseite ("left", "right", "both" oder "stop")
                duration: Laufzeit in Sekunden

        Returns:
                True bei erfolgreicher Übertragung, sonst False
        """

    @abstractmethod
    def register_callbacks(self):
        """
        Registriert Callbacks für die Verarbeitung von Protokollnachrichten.
        """

    @abstractmethod
    def add_callback(self, message_type, callback):
        """
        Fügt einen Callback für einen bestimmten Nachrichtentyp hinzu.

        Args:
                message_type: Art der Nachricht
                callback: Callback-Funktion

        Returns:
                True bei erfolgreicher Registrierung, sonst False
        """

    @abstractmethod
    def remove_callback(self, message_type, callback):
        """
        Entfernt einen Callback für einen bestimmten Nachrichtentyp.

        Args:
                message_type: Art der Nachricht
                callback: Zu entfernender Callback

        Returns:
                True bei erfolgreicher Entfernung, sonst False
        """