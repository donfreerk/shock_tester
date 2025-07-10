#!/usr/bin/env python3
"""
MQTT-Monitor für Windows
Alternative zu mosquitto_sub
"""

import paho.mqtt.client as mqtt
import json
import time

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("🔗 MQTT-Monitor verbunden")
        client.subscribe("suspension/#")
    else:
        print(f"❌ Verbindung fehlgeschlagen: {rc}")

def on_message(client, userdata, msg):
    topic = msg.topic
    try:
        payload = json.loads(msg.payload.decode())
        print(f"📡 {topic}")
        
        # Wichtige Topics hervorheben
        if "raw_data/complete" in topic:
            print(f"   📊 Raw Data: {len(payload.get('raw_data', []))} Datenpunkte")
        elif "results/processed" in topic:
            print(f"   ✅ Processed: {payload.get('test_id', 'unknown')}")
            if payload.get('results', {}).get('phase_shift_result'):
                phase = payload['results']['phase_shift_result'].get('min_phase_shift', 'N/A')
                print(f"      🎯 Phase-Shift: {phase}°")
        elif "test/start" in topic:
            print(f"   🚀 Test gestartet: {payload.get('position', 'unknown')}")
        elif "heartbeat" in topic:
            service = payload.get('service', 'unknown')
            print(f"   💓 {service} alive")
        else:
            print(f"   📋 {str(payload)[:100]}...")
            
    except json.JSONDecodeError:
        print(f"📡 {topic}: {msg.payload.decode()}")
    except Exception as e:
        print(f"📡 {topic}: Error - {e}")

def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect("localhost", 1883, 60)
        print("🎯 MQTT-Monitor gestartet (Ctrl+C zum Beenden)")
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n👋 MQTT-Monitor beendet")
    except Exception as e:
        print(f"❌ Fehler: {e}")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
