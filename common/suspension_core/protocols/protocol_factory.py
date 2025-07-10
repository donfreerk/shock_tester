def create_protocol(protocol_type, can_interface, config=None):
    """
    Erstellt eine Protokollinstanz basierend auf dem angegebenen Typ.

    Args:
            protocol_type: "asa" oder "eusama"
            can_interface: Eine Instanz der CanInterface-Klasse
            config: Optionales Konfigurationsobjekt

    Returns:
            Eine Protokollinstanz
    """
    if protocol_type.lower() == "eusama":
        from suspension_core.protocols.eusama_protocol import EusamaProtocol

        return EusamaProtocol(can_interface)

    raise ValueError(f"Unbekannter Protokolltyp: {protocol_type}")