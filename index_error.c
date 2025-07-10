//---------------------------------------------------------------------------
// XC8 Version - 32 bit evaluation von Konstanten ist Standard
//---------------------------------------------------------------------------
#include <xc.h>
#include <stdint.h>
#include <string.h>

// Define crystal frequency for delay functions
#define _XTAL_FREQ 16000000  // 16 MHz crystal

// Configuration Bits für PIC18F248 (XC8 Syntax)
#pragma config OSCS = OFF           // Oscillator Switch disabled
#pragma config OSC = HSPLL          // HS Oscillator with PLL enabled
#pragma config PWRT = ON            // Power-up Timer enabled
#pragma config BOR = ON             // Brown-out Reset enabled
#pragma config BORV = 25            // Brown-out Reset Voltage (2.5V)
#pragma config WDT = OFF            // Watchdog Timer disabled
#pragma config WDTPS = 1            // Watchdog Timer Postscale Select (1:1)
#pragma config STVR = ON            // Stack Full/Underflow will cause Reset
#pragma config LVP = OFF            // Low-Voltage ICSP disabled
#pragma config CP0 = OFF            // Code Protection Block 0 disabled
#pragma config CP1 = OFF            // Code Protection Block 1 disabled
#pragma config CPB = OFF            // Boot Block Code Protection disabled
#pragma config CPD = OFF            // Data EEPROM Code Protection disabled
#pragma config WRT0 = OFF           // Write Protection Block 0 disabled
#pragma config WRT1 = OFF           // Write Protection Block 1 disabled
#pragma config WRTB = OFF           // Boot Block Write Protection disabled
#pragma config WRTC = OFF           // Configuration Register Write Protection disabled
#pragma config WRTD = OFF           // Data EEPROM Write Protection disabled
#pragma config EBTR0 = OFF          // Table Read Protection Block 0 disabled
#pragma config EBTR1 = OFF          // Table Read Protection Block 1 disabled
#pragma config EBTRB = OFF          // Boot Block Table Read Protection disabled

typedef struct {
    uint16_t    adv;        // AD-Value (statt uns16)
    uint16_t    weight;     // zugehöriges Gewicht in kg (statt uns16)
} AD2WEIGHT; // sizeof(AD2WEIGHT) == 4

// XC8 kann mehrdimensionale Arrays UND verwaltet Memory automatisch
// Keine bank1 Direktive nötig
AD2WEIGHT  scaleAd2weight[8][4];      // Skalierfaktoren für 8 Geber, jeweils max 4 Werte
// Alternativ als 1D-Array:
// AD2WEIGHT  scaleAd2weight[8*4];    // Falls Sie die 1D-Version bevorzugen

void InitVars(void)
{
    // XC8 Alternative zu clearRAM() - globale Variablen initialisieren
    memset(scaleAd2weight, 0, sizeof(scaleAd2weight));
}

void ScalesFromCAN(void)
{
    uint8_t  geber_nummer = 0;      // Initialisiert (statt uns8)
    uint16_t ad_wert = 0, gew_wert = 0;   // Initialisiert (statt uns16)

    // XC8 Version - korrekte Pointer-Arithmetik
    // Option 1: Mit 2D-Array (einfacher und sicherer)
    if(geber_nummer < 8) {
        scaleAd2weight[geber_nummer][0].adv = ad_wert;
        scaleAd2weight[geber_nummer][0].weight = gew_wert;
    }
    
    // Option 2: Mit 1D-Array und Pointer (wie im Original)
    // AD2WEIGHT *a2w = &scaleAd2weight[geber_nummer * 4];
    // a2w->adv = ad_wert;
    // a2w->weight = gew_wert;
    
    // Option 3: Mit expliziter Index-Berechnung
    // uint8_t index = geber_nummer * 4;
    // if(index < (8*4)) {
    //     scaleAd2weight[index].adv = ad_wert;
    //     scaleAd2weight[index].weight = gew_wert;
    // }
}

void main(void)    // XC8: void main(void) statt main()
{
    InitVars();    // Ersetzt clearRAM() - initialisiert globale Variablen
    
    /* Hardware initialisieren */
    // Hier würden die Init-Funktionen stehen
    
    for(;;) {
        ScalesFromCAN();
    }
}
