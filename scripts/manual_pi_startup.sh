# A. Hardware Bridge Service manuell starten
cd /home/pi/fahrwerkstester
python -m common.suspension_core.hardware_bridge_service

# B. Pi Processing Service manuell starten (in separater Terminal-Session)
python -m backend.pi_processing_service.main

# C. Mit spezifischer Konfiguration
python -m backend.pi_processing_service.main --config config/pi_processing_config.yaml

# D. Mit Debug-Logging
PYTHONPATH=/home/pi/fahrwerkstester python -m backend.pi_processing_service.main

# E. Test der CAN-Verbindung (Python-Script)
cat << 'EOF' > test_can_connection.py
#!/usr/bin/env python3
import can
import time
import sys

def test_can_connection():
    """Testet die CAN-Verbindung"""
    print("🔍 Teste CAN-Verbindung...")
    
    try:
        # Hardware CAN testen
        bus = can.interface.Bus(channel='can0', bustype='socketcan')
        print("✅ Hardware CAN (can0) verfügbar")
        
        # Test-Nachricht senden
        msg = can.Message(arbitration_id=0x123, data=[0x11, 0x22, 0x33])
        bus.send(msg)
        print("✅ Test-Nachricht gesendet")
        
        # Kurz auf Antwort warten
        received_msg = bus.recv(timeout=1.0)
        if received_msg:
            print(f"📨 Nachricht empfangen: {received_msg}")
        else:
            print("⚠️ Keine Antwort erhalten (normal wenn keine anderen CAN-Geräte)")
            
        bus.shutdown()
        return True
        
    except Exception as e:
        print(f"❌ Hardware CAN failed: {e}")
        
        try:
            # Virtual CAN als Fallback
            bus = can.interface.Bus(channel='vcan0', bustype='socketcan')
            print("✅ Virtual CAN (vcan0) verfügbar")
            bus.shutdown()
            return True
        except Exception as e2:
            print(f"❌ Virtual CAN failed: {e2}")
            return False

if __name__ == "__main__":
    success = test_can_connection()
    sys.exit(0 if success else 1)
EOF

python test_can_connection.py