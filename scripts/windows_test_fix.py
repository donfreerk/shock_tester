#!/usr/bin/env python3
"""
Windows-Test-Fix Script
Behebt Unicode- und MQTT-Probleme für Windows-Testing
"""

import os
import sys
import subprocess
import time

def fix_console_encoding():
    """Fixiert Windows Console-Encoding für Unicode"""
    if sys.platform == "win32":
        try:
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8')
                sys.stderr.reconfigure(encoding='utf-8')
            
            os.environ['PYTHONIOENCODING'] = 'utf-8'
            print("[OK] Console-Encoding auf UTF-8 gesetzt")
            return True
        except Exception as e:
            print(f"[WARNING] Console-Encoding konnte nicht gesetzt werden: {e}")
            return False
    return True

def check_mqtt_broker():
    """Prüft ob MQTT-Broker erreichbar ist"""
    try:
        import paho.mqtt.client as mqtt
        
        client = mqtt.Client()
        client.connect("localhost", 1883, 60)
        client.disconnect()
        print("[OK] MQTT-Broker auf localhost:1883 erreichbar")
        return True
    except Exception as e:
        print(f"[ERROR] MQTT-Broker nicht erreichbar: {e}")
        print("       Starte Docker: docker run -it -p 1883:1883 eclipse-mosquitto")
        print("       Oder installiere Mosquitto: https://mosquitto.org/download/")
        return False

def start_mqtt_test():
    """Testet MQTT-Verbindung mit Test-Message"""
    try:
        import paho.mqtt.client as mqtt
        import json
        
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                print("[OK] MQTT-Test-Verbindung erfolgreich")
                client.subscribe("suspension/test/#")
            else:
                print(f"[ERROR] MQTT-Verbindung fehlgeschlagen: {rc}")
        
        def on_message(client, userdata, msg):
            print(f"[MQTT] {msg.topic}: {msg.payload.decode()}")
        
        client = mqtt.Client(client_id="windows_test_client")
        client.on_connect = on_connect
        client.on_message = on_message
        
        client.connect("localhost", 1883, 60)
        client.loop_start()
        
        # Test-Message senden
        test_msg = {
            "test_id": "windows_test_123",
            "position": "front_left", 
            "success": True,
            "results": {
                "sine_curves": {
                    "time_data": [0.0, 0.1, 0.2],
                    "platform_position": [0.0, 5.0, 0.0],
                    "tire_force": [500.0, 600.0, 500.0]
                },
                "phase_shift_result": {
                    "min_phase_shift": 42.5,
                    "evaluation": "good"
                }
            },
            "timestamp": time.time()
        }
        
        client.publish("suspension/results/processed", json.dumps(test_msg))
        print("[OK] Test-Message an GUI gesendet")
        
        time.sleep(2)
        client.loop_stop()
        client.disconnect()
        return True
        
    except Exception as e:
        print(f"[ERROR] MQTT-Test fehlgeschlagen: {e}")
        return False

def run_system_test():
    """Führt vollständigen System-Test aus"""
    print("🔧 Windows-Test-Setup für Fahrwerkstester")
    print("=" * 50)
    
    # 1. Console-Encoding
    print("\n1. Console-Encoding prüfen...")
    if not fix_console_encoding():
        print("   [WARNING] Unicode-Ausgabe könnte fehlerhaft sein")
    
    # 2. MQTT-Broker
    print("\n2. MQTT-Broker prüfen...")
    if not check_mqtt_broker():
        print("   [STOP] Bitte MQTT-Broker starten bevor Services gestartet werden")
        return False
    
    # 3. MQTT-Test
    print("\n3. MQTT-Test durchführen...")
    if not start_mqtt_test():
        print("   [WARNING] MQTT-Test fehlgeschlagen")
    
    print("\n✅ Vorbereitung abgeschlossen!")
    print("\nJetzt können die Services gestartet werden:")
    print("1. python -m backend.can_simulator_service.main --endless")
    print("2. python hardware/hardware_bridge.py --mode simulator") 
    print("3. python frontend/desktop_gui/simplified_gui.py")
    
    return True

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Windows-Test-Fix für Fahrwerkstester")
    parser.add_argument("--test-mqtt", action="store_true", help="Nur MQTT-Test durchführen")
    parser.add_argument("--fix-encoding", action="store_true", help="Nur Console-Encoding fixen")
    
    args = parser.parse_args()
    
    if args.test_mqtt:
        start_mqtt_test()
    elif args.fix_encoding:
        fix_console_encoding()
    else:
        run_system_test()
