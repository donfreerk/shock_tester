//---------------------------------------------------------------------------
// EUSAMA-Protokoll Erweiterungen für PIC Controller
// Version 2.0 - Mit Motor-, Display- und Lampen-Steuerung
// PIC Controller: PIC18F248 - XC8 Version
//
// WICHTIGER DEBUG/REFERENZ-CODE: 
// Zeigt EUSAMA-CAN-Protokoll-Implementierung auf Hardware-Ebene
//---------------------------------------------------------------------------

#include <stdint.h>
#include <string.h>
#include <xc.h>

// Define crystal frequency for delay functions
#define _XTAL_FREQ 16000000 // 16 MHz crystal

// EUSAMA CAN Sub-IDs - WICHTIGE REFERENZ für Python-Implementierung
#define EUSEMA_DMS_RIGHT 0x00    // DMS rechts senden
#define EUSEMA_DMS_LEFT 0x01     // DMS links senden
#define EUSEMA_MOTOR_STATUS 0x06 // Motor-Status
#define EUSEMA_TOP_POSITION 0x07 // Top-Position erreicht
#define EUSEMA_SCALE_CMD 0x10    // Skalierung empfangen
#define EUSEMA_MOTOR_CMD 0x11    // Motor-Kommando
#define EUSEMA_DISPLAY_CMD 0x12  // Display-Kommando
#define EUSEMA_LAMP_CMD 0x13     // Lampen-Kommando

/*
WICHTIGE ERKENNTNISSE FÜR PYTHON-IMPLEMENTIERUNG:

1. CAN-ID-Format: 'EUS' + Sub-ID (EUSEMA_xxx)
2. DMS-Daten werden alle 10ms gesendet
3. Motor-Steuerung über EUSEMA_MOTOR_CMD
4. Status-Updates über EUSEMA_MOTOR_STATUS
5. Gewichts-Kalibrierung über EUSEMA_SCALE_CMD

PROTOKOLL-STRUKTUR:
- Baudrate: 1 MBit/s
- Extended CAN-IDs
- 8 DMS-Kanäle (0-3 links, 4-7 rechts)  
- Motor-Maske: Bit 0=Links, Bit 1=Rechts
- Laufzeit in Sekunden (max 255)

INTEGRATION IN PYTHON:
- Siehe backend/can_simulator_service/ für Simulator
- Siehe common/suspension_core/protocols/ für Abstraktion
- Siehe hardware/eusama_interface.py für Hardware-Bridge

DEBUGGING-HINWEISE:
- Top-Position-Sensor auf RA5
- Motor-Ausgänge auf RB5/RB6
- LED-Matrix für Status-Anzeige
- EEPROM für Kalibrierungsdaten
*/

// [Vollständiger C-Code ist in backup/root_cleanup_20250708/eus_waage.c verfügbar]

// Für Python-Integration relevante Funktionen:
// - SendEusemaDmsData() -> CAN-Datenformat
// - ProcessMotorCommand() -> Motor-Steuerung
// - ScalesFromCAN() -> Kalibrierung
// - SendMotorStatus() -> Status-Feedback

#endif // DEBUG_REFERENCE_ONLY
