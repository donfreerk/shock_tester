"""
Desktop GUI package for the suspension tester application.

This package contains desktop GUI components for the suspension tester,
including the main suspension tester GUI and the CAN simulator GUI.
"""

# Use lazy imports to avoid immediate import errors
def run_suspension_tester_gui():
    """Run the suspension tester GUI."""
    from frontend.desktop_gui.suspension_tester_gui import main
    return main()

def run_simulator_gui():
    """Run the simulator GUI."""
    from frontend.desktop_gui.simulator_gui import main
    return main()

__all__ = ['run_suspension_tester_gui', 'run_simulator_gui']