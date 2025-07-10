//---------------------------------------------------------------------------
// Überprüft die Einzelsensoren der Kraftaufnehmer auf Plausibilität.
// In-Range: LED wird grün angezeigt, Out-Range: LED rot
// PIC Controller: PIC18F248 - XC8 Version
//
// EUSEMA-Protokoll Erweiterungen integriert
// Version 2.0 - Mit Motor-, Display- und Lampen-Steuerung
//---------------------------------------------------------------------------

#include <stdint.h>
#include <string.h>
#include <xc.h>

// Define crystal frequency for delay functions
#define _XTAL_FREQ 16000000 // 16 MHz crystal

// Configuration Bits für PIC18F248 (nur die verfügbaren)
#pragma config OSCS = OFF  // Oscillator Switch disabled
#pragma config OSC = HSPLL // HS Oscillator with PLL enabled
#pragma config PWRT = ON   // Power-up Timer enabled
#pragma config BOR = ON    // Brown-out Reset enabled
#pragma config BORV = 25   // Brown-out Reset Voltage (2.5V)
#pragma config WDT = OFF   // Watchdog Timer disabled
#pragma config WDTPS = 1   // Watchdog Timer Postscale Select (1:1)
#pragma config STVR = ON   // Stack Full/Underflow will cause Reset
#pragma config LVP = OFF   // Low-Voltage ICSP disabled
#pragma config CP0 = OFF   // Code Protection Block 0 disabled
#pragma config CP1 = OFF   // Code Protection Block 1 disabled
#pragma config CPB = OFF   // Boot Block Code Protection disabled
#pragma config CPD = OFF   // Data EEPROM Code Protection disabled
#pragma config WRT0 = OFF  // Write Protection Block 0 disabled
#pragma config WRT1 = OFF  // Write Protection Block 1 disabled
#pragma config WRTB = OFF  // Boot Block Write Protection disabled
#pragma config WRTC = OFF  // Configuration Register Write Protection disabled
#pragma config WRTD = OFF  // Data EEPROM Write Protection disabled
#pragma config EBTR0 = OFF // Table Read Protection Block 0 disabled
#pragma config EBTR1 = OFF // Table Read Protection Block 1 disabled
#pragma config EBTRB = OFF // Boot Block Table Read Protection disabled

#define ASIZE(a) (sizeof(a) / sizeof(a[0]))

#define CAN_BAUDRATE 1000000 // Bus Bitrate
#define DMS_MAX_F 750        // maximale Kraftbelastung eines DMS-Gebers in kg

// CAN Bit definitions - using XC8 syntax
#define TXB0_ABT TXB0CONbits.TXABT
#define TXB0_LARB TXB0CONbits.TXLARB
#define TXB0_ERR TXB0CONbits.TXERR
#define TXB0_REQ TXB0CONbits.TXREQ

#define TXB1_ABT TXB1CONbits.TXABT
#define TXB1_LARB TXB1CONbits.TXLARB
#define TXB1_ERR TXB1CONbits.TXERR
#define TXB1_REQ TXB1CONbits.TXREQ

#define TXB2_ABT TXB2CONbits.TXABT
#define TXB2_LARB TXB2CONbits.TXLARB
#define TXB2_ERR TXB2CONbits.TXERR
#define TXB2_REQ TXB2CONbits.TXREQ

#define RXB0OVFL COMSTATbits.RXB0OVFL
#define RXB1OVFL COMSTATbits.RXB1OVFL
#define TXBO COMSTATbits.TXBO
#define TXBP COMSTATbits.TXBP
#define RXBP COMSTATbits.RXBP
#define TXWARN COMSTATbits.TXWARN
#define RXWARN COMSTATbits.RXWARN
#define EWARN COMSTATbits.EWARN

//---------------------------------------------------------------------
// Signalzuordnungen zu Portpins (siehe auch Schaltplan)
//---------------------------------------------------------------------
#define AD_DATA1 PORTCbits.RC6
#define AD_CS1 LATCbits.LATC7 // 12 bit serieller AD-Wandler links
#define AD_DATA2 PORTBbits.RB0
#define AD_CS2 LATBbits.LATB1 // 12 bit serieller AD-Wandler rechts
#define AD_CLK LATBbits.LATB4 // gemeinsame Clockleitung

// Leuchtdiode für Problem bei Betriebsspannung
#define POWER_LED LATAbits.LATA4 // zum Schreibe Latch nehmen

// === NEUE EUSEMA-Hardware-Definitionen ===
#define MOTOR_LEFT LATBbits.LATB5  // Motor Links (Pin 26)
#define MOTOR_RIGHT LATBbits.LATB6 // Motor Rechts (Pin 27)
#define TOP_SENSOR PORTAbits.RA5   // Top-Position Sensor (Pin 7)
#define LAMP_LEFT LATBbits.LATB7   // Lampe Links (Pin 28)
#define LAMP_ENTRY LATAbits.LATA2  // Einfahrt-Lampe (Pin 4)
#define LAMP_RIGHT LATAbits.LATA1  // Lampe Rechts (Pin 3)

// === EUSEMA CAN Sub-IDs ===
#define EUSEMA_DMS_RIGHT 0x00    // DMS rechts senden
#define EUSEMA_DMS_LEFT 0x01     // DMS links senden
#define EUSEMA_MOTOR_STATUS 0x06 // Motor-Status
#define EUSEMA_TOP_POSITION 0x07 // Top-Position erreicht
#define EUSEMA_SCALE_CMD 0x10    // Skalierung empfangen
#define EUSEMA_MOTOR_CMD 0x11    // Motor-Kommando
#define EUSEMA_DISPLAY_CMD 0x12  // Display-Kommando
#define EUSEMA_LAMP_CMD 0x13     // Lampen-Kommando

uint16_t LEDS; // Bit0:LED0, ..., Bit15:LED15

uint32_t t_10ms; // alle 10 ms im Interrupt inkrementiert  (Langzeittimer)
uint8_t tcnt_10;
uint8_t tcnt_100; // läuft in 10ms Schritten bis 100 (also 1 Sekunde)
uint8_t ad_filter_anz;

volatile uint8_t t1_sync;  // jede Millisekunde durch Timerinterrupt gesetzt
volatile uint8_t t10_sync; // alle 10ms gesetzt (Timer Interrupt)
volatile uint8_t scale_changed; // wird im CAN-Interrupt gesetzt, wenn neuer
                                // Offset gekommen ist

uint16_t ad_raw[8]; // unkompensierte Werte, direkt vom ad_wandler
uint16_t ad_kanaele[8];
uint16_t ad_filter[8];
uint16_t gewichte[8];
uint32_t ad_offsets[8]; // Kraft-Offsets

// === NEUE EUSEMA-Variablen ===
typedef struct {
  uint8_t running;         // Motor läuft (0/1)
  uint16_t remaining_time; // Verbleibende Zeit in 10ms Einheiten
} MOTOR_CONTROL;

typedef struct {
  uint8_t diff_value;   // Differenz-Anzeige (0-99)
  uint16_t left_value;  // Links-Anzeige (0-999)
  uint16_t right_value; // Rechts-Anzeige (0-999)
} DISPLAY_VALUES;

MOTOR_CONTROL motor_left = {0, 0};
MOTOR_CONTROL motor_right = {0, 0};
DISPLAY_VALUES display = {0, 0, 0};
uint8_t lamp_state = 0;
uint8_t top_position_flag = 0;
uint8_t last_top_state = 0;

typedef struct {
  uint16_t adv;    // AD-Value
  uint16_t weight; // zugehöriges Gewicht in kg
} AD2WEIGHT;

// Skalierfaktoren für 8 Geber, jeweils max 4 Werte
AD2WEIGHT scaleAd2weight[8 * 4];

#define SET_CAN_SUBID(reg, sub_id)                                             \
  reg##EIDL &= 0xE0;                                                           \
  reg##EIDL |= sub_id & 0x1F

//========== Prototypes / forward declarations ==========
uint8_t ReadADValues(void);
void InitVars(void);
void ScalesFromCAN(void);
void WaitMue(uint8_t mue);
void Wait(uint16_t msec);
void ProcessMotorCommand(void);
void ProcessDisplayCommand(void);
void ProcessLampCommand(void);
void UpdateMotorTimers(void);
void SendMotorStatus(void);
void CheckTopPosition(void);
void SendTopPositionMessage(void);
void SendSystemStatus(void);

// Low priority interrupt handler
void __interrupt(low_priority) lowPriorityIntHandler(void) {
  // Timer 0 Interrupt
  if (INTCONbits.TMR0IF) {
    INTCONbits.TMR0IF = 0; // Clear Interrupt

    // nächsten Überlauf setzen
    TMR0H = (0x10000 - 9998) >> 8;
    TMR0L = (0x10000 - 9998) & 0xff;

    t10_sync = 1; // Zeichen, daß Interrupt aktiv war
    ++t_10ms;

    // Zeitzähler round robin
    if (++tcnt_10 == 10) {
      tcnt_10 = 0;
    }

    if (++tcnt_100 == 100) {
      tcnt_100 = 0;
    }
  }

  // ---------- TIMER2 Interrupt ----------
  if (PIR1bits.TMR2IF) {
    static uint16_t led_mask = 1;
    static uint8_t led_number = 0;

    PIR1bits.TMR2IF = 0; // Reset Interrupt

    t1_sync = 1; // jede Millisekunde gesetzt

    if (LEDS & led_mask) {
      // diese LED soll leuchten
      LATC &= 0xF0;       // bisherigen Wert löschen
      LATC |= led_number; // Kanal setzen
      LATCbits.LATC4 = 0; // Enable (negative Logik!)
    } else {
      LATCbits.LATC4 = 1; // disable (alles dunkel)
    }
    led_number++;
    led_mask <<= 1;
    if (led_mask == 0) {
      // shift hat die 1 rausgeschoben, neu setzen
      led_mask = 0x0001;
      led_number = 0;
    }
  }

  //---------- CAN Interrupt -----------------
  if (PIR3) {
    uint8_t ready = 0;

    do {
      uint8_t interrupt_number = CANSTAT & 0x0E;
      interrupt_number >>= 1; // Durch 2 teilen für switch

      switch (interrupt_number) {
      case 0: // no more Interrupt
        ready = 1;
        break;

      case 1: // Error
        break;

      case 2: // TXB2
        break;

      case 3: // TXB1
        PIR3bits.TXB1IF = 0;
        break;

      case 4: // TXB0, Transmit buffer 0 übertragen
        PIR3bits.TXB0IF = 0;
        break;

      case 5: // RXB1
        // === ERWEITERTE CAN-Nachrichtenverarbeitung ===
        {
          uint8_t sub_id = RXB1EIDL & 0x1F;

          switch (sub_id) {
          case EUSEMA_SCALE_CMD:
            ScalesFromCAN();
            break;
          case EUSEMA_MOTOR_CMD:
            ProcessMotorCommand();
            break;
          case EUSEMA_DISPLAY_CMD:
            ProcessDisplayCommand();
            break;
          case EUSEMA_LAMP_CMD:
            ProcessLampCommand();
            break;
          }
        }
        RXB1CON &= 0b01111110; // Receive Buffer FUL und FILHIT0 Bit löschen
        PIR3bits.RXB1IF = 0;   // Interrupt behandelt
        break;

      case 6:                  // RXB0
        RXB0CON &= 0b01111110; // Receive Buffer FUL und FILHIT0 Bit löschen
        PIR3bits.RXB0IF = 0;
        break;

      case 7: // Wake Up on Int
        break;
      }
    } while (!ready);
  }
}

void InitInterrupts(void) {
  RCONbits.IPEN = 0;   // Disable High/Low priority interrupts
  INTCONbits.GIEH = 1; // Global Interrupt Enable High
  INTCONbits.GIEL = 1; // Global Interrupt Enable Low
}

void InitTimer0(void) {
  T0CON = 0x81;           // Timer0 enable, 16bit, Prescaler 1:4, internal clock
  INTCON2bits.TMR0IP = 0; // Int Priority Low
  INTCONbits.TMR0IF = 0;  // clear timer0 interrupt flag
  INTCONbits.TMR0IE = 1;  // Enable timer-0 Interrupt
}

void InitTimer1(void) {
  T1CON = 0b10100001;
  //       ^^^ ^^^^
  //       ||| |||+---- Start Timer1
  //       ||| ||+----- Clock select, use internal FOsc/4 Clock
  //       ||| |+------ T1 Sync (not used here)
  //       ||| +------- T1 OSC enable (not used, we use FOsc)
  //       ||+--------- Presaler, we use 1:4
  //       |+---------- unimplemented
  //       +----------- RD16, TMR1H is latched when low byte is read
}

void InitTimer2(void) {
  PR2 = 250; // bei TMR2==PR2 gibt's Interrupt, so interrupted er alle 250µs
  T2CON = 0b00111101; // Timer2 Pre/Postscaler
  //       ^ ^^^^ ^ ^^
  //       | |||| | ++-- Prescaler (01 = 1:4, bei 16 Mhz im 1µs inkrement)
  //       | |||| +----- Timer2 ON
  //       | ++++------- Postscaler 1:4 (=0011)
  //       +------------ unused

  IPR1bits.TMR2IP = 0; // Int Priority LOW for Timer 2
  PIR1bits.TMR2IF = 0; // clear timer2 interrupt flag
  PIE1bits.TMR2IE = 1; // Enable timer2 Interrupt
}

// Tristates setzen
void InitIO() {
  LATA = 0;     // Latche auf 0 setzen
  TRISA = 0x2F; // untere 4 bit Analog, RA4 open Drain Leuchtdiode
  LATB = 0;     // Latche auf 0 setzen
  TRISB = 0x09; // bit 2 ist CAN-TX, bit 3 CAN-RX, Bit0 ist DATA2, Rest Ausgang
  TRISC = 0x40; // PIN6=>DATA1, alles andere Ausgang
  LATC = 0x10;  // LED ena
  AD_CS1 = 1;   // /ChipSelect auf deselect
  AD_CS2 = 1;

  // === NEUE EUSEMA I/O-Konfiguration ===
  // Motor-Ausgänge
  TRISBbits.TRISB5 = 0; // Motor Links als Ausgang
  TRISBbits.TRISB6 = 0; // Motor Rechts als Ausgang
  TRISBbits.TRISB7 = 0; // Lampe Links als Ausgang
  TRISAbits.TRISA1 = 0; // Lampe Rechts als Ausgang
  TRISAbits.TRISA2 = 0; // Einfahrt-Lampe als Ausgang

  // Top-Sensor als Eingang
  TRISAbits.TRISA5 = 1; // Top-Position als Eingang

  // Ausgänge initialisieren
  MOTOR_LEFT = 0;
  MOTOR_RIGHT = 0;
  LAMP_LEFT = 0;
  LAMP_ENTRY = 0;
  LAMP_RIGHT = 0;
}

void InitAD() {
  // Kanal AD1 wählen
  ADCON0 = 0b01001001;
  //        ^^^^ ^^ ^--  ADON (Wandler einschalten)
  //        |||| |+----  GO, /DONE
  //        ||++-+-----  Channel Select
  //        ++---------  ADCS0:ADCS1 AD-Clock Select OSC/8

  ADCON1 = 0b10001000;
  //        ^^    ^^^^--  {A0, A1, A2, A4} analog-eingang, REF=A3 (+5V)
  //        |+----------  oberes Bit von AD-Clock Select OSC/32
  //        +-----------  Format right justified

  PIR1bits.ADIF = 0; // clear Interrupt Flag
  IPR1bits.ADIP = 0; // Interrupt Priority LOW
  PIE1bits.ADIE = 0; // Disable AD Interrupt

  // externe AD-Wandler konfigurieren
  AD_CS1 = 1;
  AD_CS2 = 1;
}

#define SET_CAN_ID(reg, a, b, c, d)                                            \
  reg##EIDH = ((c) >> 3) | (uint8_t)((b) << 5);                                \
  reg##EIDL = (d) | (uint8_t)((c) << 5);                                       \
  reg##SIDH = a;                                                               \
  reg##SIDL = (((b) >> 3) & 0x03) | 0x08 | ((b) & 0xE0);

#define SET_CAN_MASK(reg, mask)                                                \
  reg##SIDH = (uint8_t)((mask >> 21) & 0xff);                                  \
  reg##SIDL = (uint8_t)(((mask >> 16) & 0x03) | (((mask >> 18) << 5) & 0xE0)); \
  reg##EIDH = (uint8_t)((mask >> 8) & 0xff);                                   \
  reg##EIDL = (uint8_t)(mask & 0xff);

#define SET_CAN_FILTER(reg, mask) SET_CAN_MASK(reg, mask)

void InitCAN() {
  CANCON &= ~0xE0;       // obere 3 Bit löschen
  CANCONbits.REQOP2 = 1; // Request configuration mode

  // warte, bis Device tatsächlich im Modus angekommen ist
  while ((CANSTAT & 0xE0) != 0x80)
    ;

#if CAN_BAUDRATE == 1000000
  // Bitrate 1 MBit/s
  BRGCON1 = 0b01000000; // SJW = 2*Tq, BRP = (2*1)/FOsc (FOsc=16MHz)
  BRGCON2 = 0b11010000; // Phase Seg2 Time freely programmable
                        // SAM, Sample time 3 times before
                        // Phase Seg1 = 3, Propagation time = 1
  BRGCON3 = 0b01000010; // use CAN WakeUp Filter, Phase Seg2 = 3
#endif

  CIOCON = 0b00100000; // CANCAP=0, CANTX-Idle = Vdd

  SET_CAN_ID(RXF0, 'E', 'U', 'S', 0x1F);
  SET_CAN_ID(RXF1, 0xff, 0xff, 0xff, 0x31);

  // Mask so setzen, dass alle Eusama Pakete empfangen werden
  SET_CAN_MASK(RXM0, 0x1FFFFFE0)
  SET_CAN_MASK(RXM1, 0x1FFFFFE0)

  // nur EUSAMA Pakete durchlassen
  SET_CAN_FILTER(RXF0, (0x455553UL << 5))
  SET_CAN_FILTER(RXF1, (0x455553UL << 5))
  SET_CAN_FILTER(RXF2, (0x455553UL << 5))
  SET_CAN_FILTER(RXF3, (0x455553UL << 5))

  SET_CAN_ID(RXF3, 'E', 'U', 'S', 0x00)

  // Receive-Buffer 0 als leer initialisieren
  RXB0CON = 0b01000000; // Receive-Buf empty, only extended ID messages
  RXB0DLC = 0;          // Data Length = 0

  // gleiches mit Puffer 1
  RXB1CON = 0b01000000;
  RXB1DLC = 0;

  PIR3 = 0;          // Interrupt-Flags löschen
  IPR3 = 0x00;       // erstmal alle als low-priority interrupts
  PIE3 = 0b00000011; // RXB0IE und RXB1IE enable

  CANCON = 0b00011100;   // request normal mode
  __delay_ms(1);         // Short delay for mode transition
  CANCONbits.REQOP0 = 0; // normal mode
}

void ReadScaleFromEEProm(void) {
  AD2WEIGHT *eev;
  uint8_t geber, adr = 0, i, j;
  uint8_t read_bytes[4];

  eev = scaleAd2weight;
  for (geber = 0; geber < 8; ++geber) {
    for (i = 0; i < 4; ++i) {
      for (j = 0; j < 4; ++j) {
        LEDS |= 0x0001; // LED0 einschalten
        EEADR = adr;
        adr++;
        EECON1bits.EEPGD = 0; // Read EEPROM
        EECON1bits.CFGS = 0;  // access EEPROM
        EECON1bits.RD = 1;    // initiate Read EEPROM
        read_bytes[j] = EEDATA;
      }
      eev->adv = ((uint16_t)read_bytes[0] << 8) | read_bytes[1];
      eev->weight = ((uint16_t)read_bytes[2] << 8) | read_bytes[3];
      eev++;
    }
  }
}

void WriteScaleToEEPROM(void) {
  if (scale_changed) {
    uint8_t geber, i, j, adr = 0;
    uint8_t towrite[4];
    AD2WEIGHT *a2w = scaleAd2weight;

    INTCONbits.GIEH = 0; // no interrupts during write
    EECON1bits.WREN = 1; // Write enable

    for (geber = 0; geber < 8; ++geber) {
      for (i = 0; i < 4; ++i) {
        towrite[0] = a2w->adv >> 8;
        towrite[1] = a2w->adv & 0xFF;
        towrite[2] = a2w->weight >> 8;
        towrite[3] = a2w->weight & 0xFF;
        a2w++;

        for (j = 0; j < 4; ++j) {
          EEADR = adr;
          EEDATA = towrite[j];
          adr++;
          EECON1bits.EEPGD = 0; // Write EEPROM
          EECON1bits.CFGS = 0;  // access EEPROM

          // required sequence
          EECON2 = 0x55;
          EECON2 = 0xAA;
          EECON1bits.WR = 1; // initiate Write
          while (EECON1bits.WR == 1)
            ; // wait until byte is written
        }
      }
    }
    INTCONbits.GIEH = 1; // Interrupts allowed again
    scale_changed = 0;   // Wert(e) geschrieben
    EECON1bits.WREN = 0; // disable writes
  }
}

uint8_t FindScaleVal(uint8_t geber, uint16_t ad2scale) {
  AD2WEIGHT *a2w;
  uint8_t idx, index, ret = 0xff;
  uint16_t adv;

  index = geber * 4;
  a2w = scaleAd2weight + index;

  for (idx = 0; idx < 4; ++idx) {
    adv = a2w->adv;
    if (adv == 0 || adv > 0x3ff) // 0 oder größer als AD auflösung
      break;
    ret = index;
    if (adv > ad2scale) {
      break;
    }
    index++;
    a2w++;
  }

  return ret;
}

void ScaleGeber(void) {
  uint8_t geber, idx;

  for (geber = 0; geber < 8; ++geber) {
    idx = FindScaleVal(geber, ad_kanaele[geber]);
    if (idx < 8 * 4) {
      uint32_t gew, sg, ad, temp;
      AD2WEIGHT *pt_found = scaleAd2weight + idx;
      sg = pt_found->weight;
      ad = (uint32_t)ad_kanaele[geber];
      ad <<= 16; // skaliert, damit Division nicht 0 wird
      temp = ad;
      temp /= pt_found->adv;
      gew = temp * sg;
      gewichte[geber] = gew >> 16;
    } else {
      gewichte[geber] = ad_kanaele[geber];
    }
  }
}

void ScalesFromCAN(void) {
  uint8_t geber_nummer, scale_index;
  uint16_t ad_wert, gew_wert;

  if ((RXB1EIDL & 0x1F) == 0x10 && (RXB1DLC & 0x0F) >= 6) {
    geber_nummer = RXB1D0;
    scale_index = RXB1D1;

    if (geber_nummer < 8 && scale_index < 4) {
      ad_wert = ((uint16_t)RXB1D2 << 8) | RXB1D3;
      gew_wert = ((uint16_t)RXB1D4 << 8) | RXB1D5;

      AD2WEIGHT *a2w;
      a2w = scaleAd2weight + geber_nummer * 4 + scale_index;
      a2w->adv = ad_wert;
      a2w->weight = gew_wert;
      scale_changed = 1;
    }
  }
}

// === NEUE EUSEMA-Funktionen ===

void ProcessMotorCommand(void) {
  if ((RXB1DLC & 0x0F) >= 2) {
    uint8_t motor_mask = RXB1D0;
    uint8_t runtime = RXB1D1;

    // Motor Links
    if (motor_mask & 0x01) {
      MOTOR_LEFT = 1;
      motor_left.running = 1;
      motor_left.remaining_time = runtime * 100; // Sekunden -> 10ms
    } else if (motor_mask == 0x00) {
      MOTOR_LEFT = 0;
      motor_left.running = 0;
      motor_left.remaining_time = 0;
    }

    // Motor Rechts
    if (motor_mask & 0x02) {
      MOTOR_RIGHT = 1;
      motor_right.running = 1;
      motor_right.remaining_time = runtime * 100;
    } else if (motor_mask == 0x00) {
      MOTOR_RIGHT = 0;
      motor_right.running = 0;
      motor_right.remaining_time = 0;
    }
  }
}

void ProcessDisplayCommand(void) {
  if ((RXB1DLC & 0x0F) >= 5) {
    display.diff_value = RXB1D0;
    display.left_value = ((uint16_t)RXB1D1 << 8) | RXB1D2;
    display.right_value = ((uint16_t)RXB1D3 << 8) | RXB1D4;

    // TODO: Hier würde die tatsächliche Display-Ansteuerung erfolgen
    // z.B. über SPI oder I2C an externe Display-Hardware
  }
}

void ProcessLampCommand(void) {
  if ((RXB1DLC & 0x0F) >= 1) {
    lamp_state = RXB1D0;

    LAMP_LEFT = (lamp_state & 0x01) ? 1 : 0;
    LAMP_ENTRY = (lamp_state & 0x02) ? 1 : 0;
    LAMP_RIGHT = (lamp_state & 0x04) ? 1 : 0;
  }
}

void UpdateMotorTimers(void) {
  // Motor Links
  if (motor_left.remaining_time > 0) {
    motor_left.remaining_time--;
    if (motor_left.remaining_time == 0) {
      MOTOR_LEFT = 0;
      motor_left.running = 0;
    }
  }

  // Motor Rechts
  if (motor_right.remaining_time > 0) {
    motor_right.remaining_time--;
    if (motor_right.remaining_time == 0) {
      MOTOR_RIGHT = 0;
      motor_right.running = 0;
    }
  }
}

void SendMotorStatus(void) {
  while (TXB0_REQ)
    ; // Warten bis Buffer frei

  SET_CAN_ID(TXB0, 'E', 'U', 'S', EUSEMA_MOTOR_STATUS);
  TXB0DLC = 2;

  // Motor-Maske erstellen
  TXB0D0 = 0;
  if (motor_left.running)
    TXB0D0 |= 0x01;
  if (motor_right.running)
    TXB0D0 |= 0x02;

  // Maximale verbleibende Zeit
  uint8_t max_time = 0;
  if (motor_left.remaining_time > motor_right.remaining_time) {
    max_time = motor_left.remaining_time / 100; // 10ms -> Sekunden
  } else {
    max_time = motor_right.remaining_time / 100;
  }
  TXB0D1 = max_time;

  TXB0_REQ = 1; // Senden
}

void CheckTopPosition(void) {
  uint8_t current_state = TOP_SENSOR;

  // Flanken-Erkennung (steigende Flanke)
  if (current_state && !last_top_state) {
    top_position_flag = 1;
    SendTopPositionMessage();
  }

  last_top_state = current_state;
}

void SendTopPositionMessage(void) {
  while (TXB1_REQ)
    ; // Warten

  SET_CAN_ID(TXB1, 'E', 'U', 'S', EUSEMA_TOP_POSITION);
  TXB1DLC = 2;

  TXB1D0 = 0x01;                     // Position erreicht
  TXB1D1 = (uint8_t)(t_10ms & 0xFF); // Zeit-Stempel

  TXB1_REQ = 1;
}

void SendSystemStatus(void) {
  while (TXB2_REQ)
    ; // Warten

  SET_CAN_ID(TXB2, 'E', 'U', 'S', 0x05); // System-Status
  TXB2DLC = 8;

  // Byte 0-1: System-Flags
  TXB2D0 = 0;
  if (motor_left.running)
    TXB2D0 |= 0x01;
  if (motor_right.running)
    TXB2D0 |= 0x02;
  if (top_position_flag)
    TXB2D0 |= 0x04;

  TXB2D1 = lamp_state;

  // Byte 2-3: Gewicht Links (Summe DMS 0-3)
  uint16_t weight_left =
      (gewichte[0] + gewichte[1] + gewichte[2] + gewichte[3]);
  TXB2D2 = weight_left >> 8;
  TXB2D3 = weight_left & 0xFF;

  // Byte 4-5: Gewicht Rechts (Summe DMS 4-7)
  uint16_t weight_right =
      (gewichte[4] + gewichte[5] + gewichte[6] + gewichte[7]);
  TXB2D4 = weight_right >> 8;
  TXB2D5 = weight_right & 0xFF;

  // Byte 6-7: Reserviert
  TXB2D6 = 0;
  TXB2D7 = 0;

  TXB2_REQ = 1;

  // Flag zurücksetzen
  top_position_flag = 0;
}

void SendEusemaDmsData(void) {
  // EUSEMA-konforme DMS-Daten senden
  // Links (ID 0x08AAAA61)
  while (TXB2_REQ)
    ;
  SET_CAN_ID(TXB2, 'E', 'U', 'S', EUSEMA_DMS_LEFT);
  TXB2DLC = 8;

  TXB2D0 = gewichte[0] >> 8;
  TXB2D1 = gewichte[0] & 0xFF;
  TXB2D2 = gewichte[1] >> 8;
  TXB2D3 = gewichte[1] & 0xFF;
  TXB2D4 = gewichte[2] >> 8;
  TXB2D5 = gewichte[2] & 0xFF;
  TXB2D6 = gewichte[3] >> 8;
  TXB2D7 = gewichte[3] & 0xFF;
  TXB2_REQ = 1;

  // Rechts (ID 0x08AAAA60)
  while (TXB0_REQ)
    ;
  SET_CAN_ID(TXB0, 'E', 'U', 'S', EUSEMA_DMS_RIGHT);
  TXB0DLC = 8;

  TXB0D0 = gewichte[4] >> 8;
  TXB0D1 = gewichte[4] & 0xFF;
  TXB0D2 = gewichte[5] >> 8;
  TXB0D3 = gewichte[5] & 0xFF;
  TXB0D4 = gewichte[6] >> 8;
  TXB0D5 = gewichte[6] & 0xFF;
  TXB0D6 = gewichte[7] >> 8;
  TXB0D7 = gewichte[7] & 0xFF;
  TXB0_REQ = 1;
}

// alle 10ms aufgerufen
void Every10ms(void) {
  // EUSEMA-konforme DMS-Daten senden
  SendEusemaDmsData();

  // Motor-Timer aktualisieren
  UpdateMotorTimers();

  // Top-Position prüfen
  CheckTopPosition();

  // Status-Nachrichten (alle 100ms)
  if (tcnt_10 == 0) {
    SendMotorStatus();
    SendSystemStatus();
  }

  // === Debug: Motor-Status auf LEDs anzeigen ===
  if (motor_left.running)
    LEDS |= 0x0001;
  else
    LEDS &= ~0x0001;
  if (motor_right.running)
    LEDS |= 0x0002;
  else
    LEDS &= ~0x0002;
  if (top_position_flag)
    LEDS |= 0x0004;
  else
    LEDS &= ~0x0004;
}

uint8_t GetBitFeld(uint16_t wert) {
  static const uint16_t werttabelle[32] = {
      3,    5,     7,     10,    14,    20,    28,    40,    55,   80,   110,
      160,  220,   310,   440,   625,   875,   1250,  1750,  2500, 3500, 5000,
      7000, 10000, 14000, 20000, 28000, 40000, 55000, 80000, 0,    0};

  uint8_t i;
  for (i = 0; i < ASIZE(werttabelle); ++i) {
    if (wert < werttabelle[i])
      return i;
  }

  return 0;
}

// Prüft Geber auf Plausibilität, liefert Bitmasken für grüne und rote LEDs
uint8_t checkSingleGeber(uint16_t *dms) {
  uint8_t error = 0;
  uint8_t r;
  uint16_t sum, min, max;

  // Minimaler und maximaler Wert der 4 Einzelgeber
  min = max = dms[0];
  if (dms[1] < min)
    min = dms[1];
  if (dms[1] > max)
    max = dms[1];
  if (dms[2] < min)
    min = dms[2];
  if (dms[2] > max)
    max = dms[2];
  if (dms[3] < min)
    min = dms[3];
  if (dms[3] > max)
    max = dms[3];

  // Gewichte addieren
  sum = dms[0] + dms[1] + dms[2] + dms[3];

  // Differenz ermitteln
  r = max - min;

  // Plausibilitätsprüfung der DMS-Geber
  if (sum < 10) {
    error = 1; // keine ausreichende Vorspannung
  } else if ((4 * r) >= sum) {
    error = 1; // zu starke Unterschiede
  }

  return error;
}

uint8_t geberstatus[2];

void CheckGeber(void) {
  uint8_t l_status, r_status;

  l_status = checkSingleGeber(&gewichte[0]); // Geber links prüfen
  r_status = checkSingleGeber(&gewichte[4]); // Geber rechts prüfen

  geberstatus[0] = l_status;
  geberstatus[1] = r_status;
}

uint8_t ReadAD(uint8_t CS_PORT, uint8_t DATA_PIN) {
  uint8_t ad_value = 0;
  uint8_t i;

  CS_PORT = 0;   // ChipSelect low
  __delay_us(2); // kurz warten
  AD_CLK = 0;    // erste Flanke

  for (i = 0; i < 12; ++i) { // 12 Bits einlesen
    __delay_us(2);
    AD_CLK = 1; // Clock High
    __delay_us(2);
    AD_CLK = 0; // Clock Low

    ad_value <<= 1;  // Platz schaffen für neues Bit
    if (DATA_PIN) {  // Datenleitung abfragen
      ad_value |= 1; // Bit setzen, wenn Datenleitung High
    }
  }

  CS_PORT = 1; // ChipSelect wieder High

  return ad_value >> 4; // nur die oberen 8 Bits verwenden
}

uint8_t ReadADValues(void) {
  uint8_t i, kanal;

  kanal = 0;
  // vier Werte vom linken AD-Wandler lesen
  for (i = 0; i < 4; ++i) {
    uint8_t val = ReadAD(AD_CS1, AD_DATA1);
    ad_raw[kanal++] = val;
  }

  // vier Werte vom rechten AD-Wandler lesen
  for (i = 0; i < 4; ++i) {
    uint8_t val = ReadAD(AD_CS2, AD_DATA2);
    ad_raw[kanal++] = val;
  }

  return kanal;
}

// alle 1 ms aufrufen
void Every_ms(void) {
  uint8_t i;

  ReadADValues();
  LEDS &= 0xff00; // untere 8 Bits löschen

  // AD-Werte kompensieren
  for (i = 0; i < 8; ++i) {
    int16_t temp = ad_raw[i];
    temp -= (ad_offsets[i] >> 8);
    if (temp < 0)
      temp = 0;
    ad_kanaele[i] = temp;
  }

  ScaleGeber();
  CheckGeber();

  // Grüne oder rote LED anzeigen
  if (!geberstatus[0])
    LEDS |= 0x00f0;
  else
    LEDS |= 0x000f;
  if (!geberstatus[1])
    LEDS |= 0xf000;
  else
    LEDS |= 0x0f00;
}

void WaitMue(uint8_t mue) {
  while (mue--) {
    __delay_us(1);
  }
}

void Wait(uint16_t msec) {
  while (msec--) {
    __delay_ms(1);
  }
}

void CalcOffsetAD(void) {
  uint8_t kanal;
  uint16_t count;

  // Werte aufsummieren
  for (count = 0; count < 1000; ++count) {
    ReadADValues();
    for (kanal = 0; kanal < 8; ++kanal) {
      ad_offsets[kanal] += ad_raw[kanal];
    }
    Wait(1);
  }

  // normieren (Durchschnitt)
  for (kanal = 0; kanal < 8; ++kanal) {
    ad_offsets[kanal] /= 1000;
    ad_offsets[kanal] <<= 8;
  }
}

void InitVars(void) {
  // XC8 kann globale Arrays initialisieren, aber wir machen es explizit
  memset(ad_raw, 0, sizeof(ad_raw));
  memset(ad_kanaele, 0, sizeof(ad_kanaele));
  memset(ad_filter, 0, sizeof(ad_filter));
  memset(gewichte, 0, sizeof(gewichte));
  memset(ad_offsets, 0, sizeof(ad_offsets));
  memset(scaleAd2weight, 0, sizeof(scaleAd2weight));

  LEDS = 0;
  t_10ms = 0;
  tcnt_10 = 0;
  tcnt_100 = 0;
  ad_filter_anz = 0;
  t1_sync = 0;
  t10_sync = 0;
  scale_changed = 0;
}

void main(void) {
  POWER_LED = 0; // dauernd AN (Open Collector)

  // Hardware initialisieren
  InitVars(); // globale Variable initialisieren
  InitIO();   // Erweiterte I/O-Initialisierung für EUSEMA
  InitAD();
  InitInterrupts(); // Prioritätensystem freischalten
  InitTimer0();     // generelles 10ms Timing
  InitTimer1();
  InitTimer2(); // 1ms timer für Decoder
  ReadScaleFromEEProm();
  InitCAN(); // integrierten CAN Controller initialisieren

  Wait(5000);     // 5 Sekunden warten, damit die Geber sich 'setzen'
  CalcOffsetAD(); // Vorlasten der Geber bestimmen
  LEDS |= 0xff00; // obere 8 LEDs leuchten lassen als Zeichen,
                  // dass die Messung beginnt

  for (;;) {
    WriteScaleToEEPROM(); // wenn sich was geändert hat, die Werte schreiben

    if (t1_sync) {
      // jede Millisekunde ausführen
      Every_ms();
      t1_sync = 0;
    }

    if (t10_sync) {
      // Aufruf von Routinen, die alle 10 ms laufen sollen
      Every10ms(); // Erweiterte EUSEMA-Funktionen
      t10_sync = 0;
    }
  }
}