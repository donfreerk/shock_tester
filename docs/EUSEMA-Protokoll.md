# Übersetzung: CAN-Protokoll Eusama-Test

## Einleitung

Der Schrank für den EUSAM-Test basiert auf dem Schrank, den wir für unseren Boge-basierten Stoßdämpfertester verwenden. Daher können die Motoren (links/rechts) gestartet und gestoppt werden, und die digitalen Anzeigen können eingestellt werden, um Gewicht oder Amplitude anzuzeigen. Dieses Dokument ist ein Vorschlag für die CAN-Nachrichten. In diesem Vorschlag ist der Schrank sehr einfach gehalten, die eigentliche Skalierung und Verarbeitung erfolgt extern (RasPi?!). Der Schrank muss in der Lage sein, die Motoren/Wechselrichter über CAN-Request zu starten. Dies muss noch spezifiziert werden.

## Allgemeine Informationen zur CAN-Schnittstelle

**[WICHTIG]** Der CAN-Bus arbeitet mit der höchsten Bitrate von **1 Mbit/s**. Es werden erweiterte (29-Bit) IDs verwendet.

**[WICHTIG]** Die Nachrichten-IDs beginnen alle mit dem ASCII-Code 'EUS' (24-Bit) und einem 5-Bit Subcode zur Kennzeichnung der auszuführenden Funktion.
Beispiel: Eusama Nachrichten-ID #0 ist 0x08AAAA60

Es wurde definiert, dass Nachrichten-Sub-IDs im Bereich 0..15 vom Schrank an einen beliebigen Empfänger gesendet werden und Nachrichten-Sub-IDs im Bereich 16..31 vom externen Gerät (z.B. RasPi) an den Schrank gesendet werden.

Konventionsgemäß liegen Nachrichten vom Schrank an externe Geräte im Bereich 0x8AAAA60 .. 0x8AAAA6F und Nachrichten von externen Geräten an den Schrank im Bereich 0x8AAAA70 bis 0x8AAAA7F. Mehrere Nachrichten-IDs werden nicht verwendet und sind für zukünftige Erweiterungen frei.

## Messpunkte vom Schrank gesendet

**[WICHTIG]** Die Messung erfolgt in einem **10 ms Zyklus**. Daher erhält man **100 Punkte/Sekunde** (Ist das genug?). Ein Messpunkt besteht aus 2 CAN-Nachrichten, eine Nachricht für jede Seite. Ein Messpunkt ist definiert als:

| Wert | Bytes | Beschreibung |
|------|-------|--------------|
| AD-Wert links | 2 | AD-Wert DMS 1 (Roher AD-Wert (Bereich: 0..1023)) |
| AD-Wert links | 2 | AD-Wert DMS 2 (Roher AD-Wert (Bereich: 0..1023)) |
| AD-Wert links | 2 | AD-Wert DMS 3 (Roher AD-Wert (Bereich: 0..1023)) |
| AD-Wert links | 2 | AD-Wert DMS 4 (Roher AD-Wert (Bereich: 0..1023)) |
| AD-Wert rechts | 2 | AD-Wert DMS 5 (Roher AD-Wert (Bereich: 0..1023)) |
| AD-Wert rechts | 2 | AD-Wert DMS 6 (Roher AD-Wert (Bereich: 0..1023)) |
| AD-Wert rechts | 2 | AD-Wert DMS 7 (Roher AD-Wert (Bereich: 0..1023)) |
| AD-Wert rechts | 2 | AD-Wert DMS 8 (Roher AD-Wert (Bereich: 0..1023)) |

**[WICHTIG]** Paket 0 (ID=0x08AAAA60), Länge=8:
| Daten-Byte | Bedeutung |
|------------|-----------|
| 0 | AD-Wert High Byte links DMS 1 |
| 1 | AD-Wert Low Byte links DMS 1 |
| 2 | AD-Wert High Byte links DMS 2 |
| 3 | AD-Wert Low Byte links DMS 2 |
| 4 | AD-Wert High Byte links DMS 3 |
| 5 | AD-Wert Low Byte links DMS 3 |
| 6 | AD-Wert High Byte links DMS 4 |
| 7 | AD-Wert Low Byte links DMS 4 |

Paket 1 (ID=0x08AAAA61), Länge=8:
| Daten-Byte | Bedeutung |
|------------|-----------|
| 0 | AD-Wert High Byte rechts DMS 5 |
| 1 | AD-Wert Low Byte rechts DMS 5 |
| 2 | AD-Wert High Byte rechts DMS 6 |
| 3 | AD-Wert Low Byte rechts DMS 6 |
| 4 | AD-Wert High Byte rechts DMS 7 |
| 5 | AD-Wert Low Byte rechts DMS 7 |
| 6 | AD-Wert High Byte rechts DMS 8 |
| 7 | AD-Wert Low Byte rechts DMS 8 |

## Motoren starten/stoppen

**[WICHTIG]** Die Motoren können einzeln gestartet und gestoppt werden. Die CAN-Nachricht zum Starten/Stoppen wird vom externen Gerät (z.B. PC) gesendet.

Motor-Nachricht (ID=0x08AAAA71), Länge=2:
| Daten-Byte | Bedeutung |
|------------|-----------|
| 0 | Motor-Maske |
| 1 | Laufzeit des Motors (in Sekunden) |

Motor-Maske:
- 0x00: Alle Motoren stoppen
- 0x01: Linker Motor starten
- 0x02: Rechter Motor starten
- 0x03: Beide Motoren starten (nicht sinnvoll)

Motor-Laufzeit (Daten-Byte 1):
Zeit, die der Motor laufen soll. Nach Ablauf dieser Zeit stoppt der Motor automatisch. Es ist möglich, den Motor vorzeitig zu stoppen, indem dieses Paket mit einer Motor-Maske von 0x00 gesendet wird. Die Zeit wird in diesem Fall ignoriert!

## Überprüfen, welcher Motor läuft und wie lange

Wenn ein Motor gestartet wird, kann überprüft werden, ob der Motor läuft und wie lange er noch laufen wird. Diese Nachricht wird kontinuierlich vom Schrank alle 100 ms gesendet.

Motor-Status:
Motor-Nachricht (ID=0x08AAAA66), Länge=2:
| Daten-Byte | Bedeutung |
|------------|-----------|
| 0 | Motor-Maske |
| 1 | Verbleibende Zeit (in Sekunden) |

Motor-Maske:
- 0x00: Kein Motor läuft
- 0x01: Linker Motor läuft
- 0x02: Rechter Motor läuft
- 0x03: Beide Motoren laufen (nicht sinnvoll)

## Lampen ein-/ausschalten

**[WICHTIG]** Die Lampen am Schrank können per Fernbedienung ein- und ausgeschaltet werden. Der Schrank selbst schaltet keine Lampe ein!

Lampen-Nachricht (ID=0x08AAAA73), Länge=1:
| Daten-Byte | Bedeutung |
|------------|-----------|
| 0 | Lampen-Maske |

Lampen-Maske:
- 0x01: Lampe links
- 0x02: Einfahrlampe (grüne Lampe)
- 0x04: Lampe rechts

Wenn Sie mehrere Lampen einschalten möchten, können Sie die Lampen mit bitweisem ODER kombinieren. Wenn Sie die linke und rechte Lampe einschalten möchten, senden Sie den Wert 0x01 | 0x04 = 0x05.
Nicht gesetzte Bits schalten die entsprechende Lampe aus!

## Display-Einstellung

**[WICHTIG]** Es gibt drei Displays am Schrank. Das Display in der Mitte ist das Differenz-Display (2 Ziffern). Die linken und rechten Displays (3 Ziffern) werden normalerweise verwendet, um das Gewicht jeder Achse oder das Ergebnis der Messung anzuzeigen. Die angezeigten Werte bleiben erhalten, bis sie vom Remote-Gerät geändert werden. Alle drei Displays werden mit einem CAN-Paket eingestellt. Um nur ein Display einzustellen, müssen auch die anderen (2) Display-Werte gesetzt/wiederholt werden. Es ist nicht möglich, nur ein einzelnes Display einzustellen!

Display-Nachricht (ID=0x08AAAA72), Länge=5:
| Daten-Byte | Bedeutung |
|------------|-----------|
| 0 | Differenz-Display |
| 1 | High Byte linkes Display |
| 2 | Low Byte linkes Display |
| 3 | High Byte rechtes Display |
| 4 | Low Byte rechtes Display |

Differenz-Display: Wert von 0 bis 99
Linkes/rechtes Display: Wert von 0 bis 999

Es ist nicht möglich, nur ein Display allein einzustellen. In diesem Fall müssen die anderen Werte wiederholt werden!

## Oberste Position der Platte

**[WICHTIG]** Jedes Mal, wenn die oberste Position der linken/rechten Platte erreicht wird, wird ein CAN-Paket gesendet:

Oberste Positions-Paket, Nachricht (ID=0x08AAAA67), Länge=1:
| Daten-Byte | Bedeutung |
|------------|-----------|
| 0 | Linke/rechte oberste Position |

Bitmaske in Byte #0:
- 0x01: Linke Platte hat oberste Position erreicht
- 0x02: Rechte Platte hat oberste Position erreicht

Da intern die Erkennung mit einem Interrupt-Handler für jede Seite implementiert ist, können diese Interrupts nicht gleichzeitig behandelt werden und es kann nur ein Bit gleichzeitig gesetzt werden. Da sich nur eine Platte bewegt, ist dies irrelevant.

---

### Besonders wichtige Punkte für das Fahrwerkstester-Projekt:

1. **CAN-Konfiguration**: 1 Mbit/s Bitrate, Extended 29-Bit IDs, ASCII-Code 'EUS' als Basis
2. **Messpunkt-Struktur**: 100 Punkte/Sekunde, bestehend aus 2 CAN-Nachrichten (links/rechts)
3. **Motorsteuerung**: Individuelles Starten/Stoppen der Motoren mit einstellbarer Laufzeit
4. **Sensor-Daten**: 8 AD-Werte (DMS 1-8) mit Bereich 0-1023, verteilt auf linke und rechte Seite
5. **Obere Plattenposition**: Spezielle Nachricht wenn obere Position erreicht wird (wichtig für Testsequenzierung)
6. **Displays & Lampen**: Steuerung zur Anzeige von Testergebnissen und Benutzerführung