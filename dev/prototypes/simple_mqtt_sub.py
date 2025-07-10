#!/usr/bin/env python3
"""
Ultra-einfacher MQTT Subscriber ohne externe Dependencies
Verwendet nur Python Standard-Library
"""

import socket
import json
from datetime import datetime
import struct
import time


class SimpleMQTTSubscriber:
    def __init__(self, broker="localhost", port=1883):
        self.broker = broker
        self.port = port
        self.sock = None
        self.connected = False

    def connect(self):
        """Einfache MQTT-Verbindung"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.broker, self.port))

            # MQTT CONNECT Paket senden (vereinfacht)
            client_id = f"python_sub_{int(time.time())}"
            connect_packet = self._build_connect_packet(client_id)
            self.sock.send(connect_packet)

            # CONNACK empfangen
            response = self.sock.recv(1024)
            if len(response) >= 4 and response[3] == 0:
                print(f"✅ Verbunden mit {self.broker}:{self.port}")
                self.connected = True
                return True
            else:
                print("❌ Verbindung fehlgeschlagen")
                return False

        except Exception as e:
            print(f"❌ Verbindungsfehler: {e}")
            return False

    def subscribe(self, topic):
        """Topic abonnieren"""
        if not self.connected:
            return False

        try:
            subscribe_packet = self._build_subscribe_packet(topic)
            self.sock.send(subscribe_packet)
            print(f"📡 Abonniert: {topic}")
            return True
        except Exception as e:
            print(f"❌ Subscribe-Fehler: {e}")
            return False

    def listen(self):
        """Auf Nachrichten hören"""
        print("🎧 Warte auf Nachrichten...")
        print("⌨️  Ctrl+C zum Beenden")
        print("-" * 50)

        try:
            while True:
                data = self.sock.recv(1024)
                if data:
                    self._handle_message(data)
        except KeyboardInterrupt:
            print("\n🛑 Beendet durch Benutzer")
        except Exception as e:
            print(f"❌ Fehler beim Empfangen: {e}")
        finally:
            if self.sock:
                self.sock.close()

    def _build_connect_packet(self, client_id):
        """MQTT CONNECT Paket erstellen"""
        # Vereinfachtes MQTT CONNECT Paket
        protocol_name = b"MQTT"
        protocol_version = 4
        connect_flags = 0x02  # Clean session
        keep_alive = 60

        payload = len(client_id).to_bytes(2, "big") + client_id.encode()

        variable_header = (
            len(protocol_name).to_bytes(2, "big")
            + protocol_name
            + protocol_version.to_bytes(1, "big")
            + connect_flags.to_bytes(1, "big")
            + keep_alive.to_bytes(2, "big")
        )

        remaining_length = len(variable_header) + len(payload)
        fixed_header = b"\x10" + self._encode_remaining_length(remaining_length)

        return fixed_header + variable_header + payload

    def _build_subscribe_packet(self, topic):
        """MQTT SUBSCRIBE Paket erstellen"""
        packet_id = 1

        payload = (
            len(topic).to_bytes(2, "big") + topic.encode() + b"\x00"  # QoS 0
        )

        variable_header = packet_id.to_bytes(2, "big")
        remaining_length = len(variable_header) + len(payload)
        fixed_header = b"\x82" + self._encode_remaining_length(remaining_length)

        return fixed_header + variable_header + payload

    def _encode_remaining_length(self, length):
        """MQTT Remaining Length kodieren"""
        result = b""
        while length > 0:
            byte = length % 128
            length = length // 128
            if length > 0:
                byte |= 0x80
            result += bytes([byte])
        return result

    def _handle_message(self, data):
        """MQTT-Nachricht verarbeiten"""
        if len(data) < 2:
            return

        # Vereinfachte MQTT PUBLISH Nachricht parsen
        if data[0] & 0xF0 == 0x30:  # PUBLISH
            try:
                # Topic-Länge lesen
                topic_len = struct.unpack(">H", data[2:4])[0]
                topic = data[4 : 4 + topic_len].decode()

                # Payload extrahieren
                payload_start = 4 + topic_len
                payload = data[payload_start:].decode("utf-8", errors="ignore")

                # Nachricht anzeigen
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] {topic}")

                try:
                    # JSON formatieren wenn möglich
                    json_data = json.loads(payload)
                    print(json.dumps(json_data, indent=2, ensure_ascii=False))
                except:
                    print(payload)

                print("-" * 50)

            except Exception as e:
                print(f"❌ Nachricht-Parse-Fehler: {e}")


def main():
    """Hauptfunktion"""
    subscriber = SimpleMQTTSubscriber()
    if subscriber.connect():
        if subscriber.subscribe("suspension/#"):
            subscriber.listen()
    else:
        print(
            "❌ Kann nicht verbinden. Stellen Sie sicher, dass ein MQTT-Broker läuft:"
        )
        print("   docker run -d -p 1883:1883 eclipse-mosquitto")


if __name__ == "__main__":
    main()
