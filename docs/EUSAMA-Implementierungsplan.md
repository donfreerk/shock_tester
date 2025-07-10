# EUSAMA-Implementierungsplan

## 🎯 Ziel: Vollständiges EUSAMA-System

Sie haben bereits **70% der Funktionalität** - hier ist der Plan für die restlichen 30%:

## 📋 Phase 1: CAN-Protokoll vervollständigen

### **1.1 Erweiterte CAN-Empfangs-Handler**
```c
void ExtendedCANHandler(void) {
    uint8_t sub_id = RXB1EIDL & 0x1F;
    
    switch(sub_id) {
        case 0x10: ScalesFromCAN(); break;      // ✅ Bereits implementiert
        case 0x11: MotorFromCAN(); break;       // 🔲 Neu implementieren  
        case 0x12: DisplayFromCAN(); break;     // 🔲 Neu implementieren
        case 0x13: LampsFromCAN(); break;       // 🔲 Neu implementieren
    }
}
```

### **1.2 Motor-Steuerung via CAN**
```c
// CAN-Message: ID 0x8AAAA71, 2 Bytes
// Byte 0: Motor-Maske (Bit0=Links, Bit1=Rechts)  
// Byte 1: Laufzeit in Sekunden (0=Stop)

typedef struct {
    uint8_t motor_mask;
    uint8_t duration;
    uint8_t remaining_time;
} MOTOR_CONTROL;

MOTOR_CONTROL motor_left, motor_right;
```

### **1.3 Display-Steuerung via CAN**
```c
// CAN-Message: ID 0x8AAAA72, 5 Bytes
// Byte 0: Differenz-Display (0-99)
// Bytes 1-2: Links-Display (0-999)
// Bytes 3-4: Rechts-Display (0-999)

typedef struct {
    uint8_t  diff_display;      // 0-99
    uint16_t left_display;      // 0-999  
    uint16_t right_display;     // 0-999
} DISPLAY_VALUES;
```

## 📋 Phase 2: Hardware-Treiber implementieren

### **2.1 Motor-Hardware (Relais/Wechselrichter)**
```c
// Hardware-Ansteuerung für Motoren
#define MOTOR_LEFT_PIN   LATBbits.LATB5  
#define MOTOR_RIGHT_PIN  LATBbits.LATB6

void StartMotor(uint8_t motor, uint8_t duration) {
    if(motor & 0x01) {
        MOTOR_LEFT_PIN = 1;     // Motor links an
        motor_left.remaining_time = duration;
    }
    if(motor & 0x02) {
        MOTOR_RIGHT_PIN = 1;    // Motor rechts an  
        motor_right.remaining_time = duration;
    }
}

void StopMotor(uint8_t motor) {
    if(motor & 0x01) MOTOR_LEFT_PIN = 0;
    if(motor & 0x02) MOTOR_RIGHT_PIN = 0;
}
```

### **2.2 7-Segment Display-Treiber**
```c
// 3 Displays: Links(3-stellig), Mitte(2-stellig), Rechts(3-stellig)
uint8_t display_segments[8] = {0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07};
//                             0     1     2     3     4     5     6     7

void UpdateDisplay(uint8_t display_nr, uint16_t value) {
    // BCD-Dekodierung + Multiplexing
    uint8_t hundreds = value / 100;
    uint8_t tens = (value / 10) % 10;  
    uint8_t ones = value % 10;
    
    // Ausgabe an entsprechende Display-Ports
}
```

### **2.3 Lampen-Steuerung**
```c
// 3 Lampen: Links, Einfahrt(Grün), Rechts
#define LAMP_LEFT    LATAbits.LATA0
#define LAMP_ENTRY   LATAbits.LATA1  // Grüne Einfahrlampe
#define LAMP_RIGHT   LATAbits.LATA2

void SetLamps(uint8_t lamp_mask) {
    LAMP_LEFT  = (lamp_mask & 0x01) ? 1 : 0;
    LAMP_ENTRY = (lamp_mask & 0x02) ? 1 : 0; 
    LAMP_RIGHT = (lamp_mask & 0x04) ? 1 : 0;
}
```

### **2.4 Positions-Sensoren**
```c
// Interrupts für obere Platten-Position
void __interrupt() PositionIntHandler(void) {
    if(INT0IF) {  // Linke Platte oben
        INT0IF = 0;
        SendTopPosition(0x01);
    }
    if(INT1IF) {  // Rechte Platte oben  
        INT1IF = 0;
        SendTopPosition(0x02);
    }
}

void SendTopPosition(uint8_t position_mask) {
    // CAN-Message: ID 0x8AAAA67, 1 Byte
    TXB0D0 = position_mask;
    SET_CAN_ID(TXB0, 'E', 'U', 'S', 7);
    TXB0DLC = 1;
    TXB0_REQ = 1;
}
```

## 📋 Phase 3: Integration und Test

### **3.1 Erweiterte Timer-Funktionen**
```c
void Every100ms(void) {
    SendMotorStatus();      // Motor-Status senden
    UpdateMotorTimers();    // Laufzeit-Timer verwalten
    CheckSystemHealth();    // Fehlerdiagnose
}

void UpdateMotorTimers(void) {
    if(motor_left.remaining_time > 0) {
        motor_left.remaining_time--;
        if(motor_left.remaining_time == 0) {
            StopMotor(0x01);  // Auto-Stop nach Ablauf
        }
    }
    // Gleiches für rechten Motor
}
```

### **3.2 Status-Überwachung**
```c
void SendMotorStatus(void) {
    // CAN-Message: ID 0x8AAAA66, 2 Bytes
    uint8_t running_mask = 0;
    uint8_t remaining = 0;
    
    if(motor_left.remaining_time > 0) {
        running_mask |= 0x01;
        remaining = motor_left.remaining_time;
    }
    if(motor_right.remaining_time > 0) {
        running_mask |= 0x02;  
        remaining = motor_right.remaining_time;
    }
    
    TXB0D0 = running_mask;
    TXB0D1 = remaining;
    SET_CAN_ID(TXB0, 'E', 'U', 'S', 6);
    TXB0DLC = 2;
    TXB0_REQ = 1;
}
```

## 🛠️ Implementierungs-Reihenfolge:

### **Woche 1: CAN-Protokoll**
✅ Motor-CAN-Empfang  
✅ Display-CAN-Empfang  
✅ Lampen-CAN-Empfang  
✅ Positions-CAN-Sendung  

### **Woche 2: Hardware-Treiber**  
✅ Motor-Relais/Ports  
✅ 7-Segment Displays  
✅ Lampen-Ansteuerung  
✅ Positions-Interrupts  

### **Woche 3: Integration**
✅ Timer-Erweiterungen  
✅ Status-Überwachung  
✅ Fehlerbehandlung  
✅ Test mit Dummy-PC  

### **Woche 4: Systemtest**
✅ Hardware-in-the-Loop  
✅ Vollständiger EUSAMA-Test  
✅ Optimierung + Bugfixes  

## 💡 Empfehlung:

**Beginnen Sie mit Phase 1** - erweitern Sie den CAN-Handler für die fehlenden Messages. Das können Sie auch **ohne Hardware** testen, indem Sie CAN-Messages über einen CAN-Adapter senden.

**Ihr aktueller Code ist eine sehr solide Basis!** Die Mess-Kette funktioniert bereits perfekt. 🎉