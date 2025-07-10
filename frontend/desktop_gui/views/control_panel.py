"""
Control Panel View for EGEA Suspension Tester.

Responsibility: Test control UI components (start/stop, position selection, emergency controls).
No business logic - only UI and callback forwarding.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ControlPanel:
    """
    Control panel for test execution and system control.
    
    Features:
    - Test start/stop controls
    - Position selection (left/right/both)
    - Vehicle type selection
    - Emergency stop
    - Test configuration
    """
    
    def __init__(self, parent: tk.Widget):
        self.parent = parent
        
        # Callbacks to presenter (injected later)
        self.on_start_test: Optional[Callable] = None
        self.on_stop_test: Optional[Callable] = None
        self.on_emergency_stop: Optional[Callable] = None
        self.on_clear_buffer: Optional[Callable] = None
        self.on_send_command: Optional[Callable] = None
        
        # UI Variables
        self.position_var = tk.StringVar(value="left")
        self.vehicle_var = tk.StringVar(value="M1")
        self.test_duration_var = tk.StringVar(value="30")
        self.test_active_var = tk.BooleanVar(value=False)
        
        # UI Components
        self.start_button = None
        self.stop_button = None
        self.emergency_button = None
        self.position_combo = None
        self.vehicle_combo = None
        self.duration_entry = None
        
        self._setup_ui()
        self._update_button_states()
        
        logger.info("ControlPanel initialized")
    
    def _setup_ui(self):
        """Creates the control panel UI."""
        # Main control frame
        control_frame = ttk.LabelFrame(self.parent, text="🎮 Test Control", padding="15")
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Test configuration section
        self._setup_test_config(control_frame)
        
        # Control buttons section
        self._setup_control_buttons(control_frame)
        
        # Emergency and utility section
        self._setup_emergency_section(control_frame)
    
    def _setup_test_config(self, parent):
        """Creates test configuration section."""
        config_frame = ttk.LabelFrame(parent, text="⚙️ Test Configuration", padding="10")
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Grid layout for compact arrangement
        config_grid = ttk.Frame(config_frame)
        config_grid.pack(fill=tk.X)
        
        # Position selection
        ttk.Label(config_grid, text="Position:").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 10), pady=5)
        
        self.position_combo = ttk.Combobox(
            config_grid, textvariable=self.position_var,
            values=["left", "right", "both"], 
            state="readonly", width=8
        )
        self.position_combo.grid(row=0, column=1, padx=(0, 20), pady=5)
        
        # Vehicle type selection
        ttk.Label(config_grid, text="Vehicle:").grid(
            row=0, column=2, sticky=tk.W, padx=(0, 10), pady=5)
        
        self.vehicle_combo = ttk.Combobox(
            config_grid, textvariable=self.vehicle_var,
            values=["M1", "N1", "M2", "N2"], 
            state="readonly", width=8
        )
        self.vehicle_combo.grid(row=0, column=3, padx=(0, 20), pady=5)
        
        # Test duration
        ttk.Label(config_grid, text="Duration (s):").grid(
            row=0, column=4, sticky=tk.W, padx=(0, 10), pady=5)
        
        self.duration_entry = ttk.Entry(
            config_grid, textvariable=self.test_duration_var, 
            width=8, validate="key"
        )
        self.duration_entry.grid(row=0, column=5, pady=5)
        
        # Validation for duration entry (numbers only)
        vcmd = (self.duration_entry.register(self._validate_duration), '%P')
        self.duration_entry.config(validatecommand=vcmd)
    
    def _setup_control_buttons(self, parent):
        """Creates main control buttons."""
        button_frame = ttk.LabelFrame(parent, text="▶️ Test Control", padding="10")
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Button grid
        btn_grid = ttk.Frame(button_frame)
        btn_grid.pack(fill=tk.X)
        
        # Start test button
        self.start_button = ttk.Button(
            btn_grid, text="🚀 Start Test", 
            command=self._on_start_click,
            style="Accent.TButton"
        )
        self.start_button.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="ew")
        
        # Stop test button
        self.stop_button = ttk.Button(
            btn_grid, text="⏹️ Stop Test", 
            command=self._on_stop_click,
            state=tk.DISABLED
        )
        self.stop_button.grid(row=0, column=1, padx=(0, 10), pady=5, sticky="ew")
        
        # Clear buffer button
        clear_button = ttk.Button(
            btn_grid, text="🗑️ Clear Data", 
            command=self._on_clear_click
        )
        clear_button.grid(row=0, column=2, padx=(0, 10), pady=5, sticky="ew")
        
        # Configure grid weights for equal button sizes
        for i in range(3):
            btn_grid.grid_columnconfigure(i, weight=1)
    
    def _setup_emergency_section(self, parent):
        """Creates emergency controls and utilities."""
        emergency_frame = ttk.LabelFrame(parent, text="🚨 Emergency & Utilities", padding="10")
        emergency_frame.pack(fill=tk.X)
        
        # Emergency grid
        emr_grid = ttk.Frame(emergency_frame)
        emr_grid.pack(fill=tk.X)
        
        # Emergency stop (prominent)
        self.emergency_button = ttk.Button(
            emr_grid, text="🛑 EMERGENCY STOP", 
            command=self._on_emergency_click,
            style="Toolbutton"  # Different style for emergency
        )
        self.emergency_button.grid(row=0, column=0, padx=(0, 20), pady=5, sticky="ew")
        
        # Configure emergency button appearance
        self.emergency_button.configure(
            # Red background for emergency
            # Note: Styling depends on theme, fallback to command emphasis
        )
        
        # Quick commands
        command_frame = ttk.Frame(emr_grid)
        command_frame.grid(row=0, column=1, sticky="ew", padx=(20, 0))
        
        ttk.Label(command_frame, text="Quick Commands:").pack(anchor=tk.W)
        
        cmd_buttons = ttk.Frame(command_frame)
        cmd_buttons.pack(fill=tk.X, pady=(5, 0))
        
        # Quick command buttons
        ttk.Button(cmd_buttons, text="💡 Test MQTT", 
                  command=lambda: self._send_quick_command("test_mqtt"),
                  width=12).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(cmd_buttons, text="📊 Status", 
                  command=lambda: self._send_quick_command("get_status"),
                  width=12).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(cmd_buttons, text="🔄 Reset", 
                  command=lambda: self._send_quick_command("reset"),
                  width=12).pack(side=tk.LEFT)
        
        # Configure grid weights
        emr_grid.grid_columnconfigure(1, weight=1)
    
    def _validate_duration(self, value: str) -> bool:
        """Validates duration input (numbers only)."""
        if value == "":
            return True
        try:
            float(value)
            return True
        except ValueError:
            return False
    
    def _on_start_click(self):
        """Handles start test button click."""
        if self.on_start_test:
            # Collect test parameters
            params = {
                'position': self.position_var.get(),
                'vehicle_type': self.vehicle_var.get(),
                'duration': float(self.test_duration_var.get() or 30),
                'timestamp': self._get_timestamp()
            }
            
            logger.info(f"Start test requested with params: {params}")
            self.on_start_test(params)
    
    def _on_stop_click(self):
        """Handles stop test button click."""
        if self.on_stop_test:
            logger.info("Stop test requested")
            self.on_stop_test()
    
    def _on_emergency_click(self):
        """Handles emergency stop button click."""
        if self.on_emergency_stop:
            logger.warning("Emergency stop requested")
            self.on_emergency_stop()
    
    def _on_clear_click(self):
        """Handles clear buffer button click."""
        if self.on_clear_buffer:
            logger.info("Clear buffer requested")
            self.on_clear_buffer()
    
    def _send_quick_command(self, command_type: str):
        """Sends quick command via callback."""
        if self.on_send_command:
            command = {
                'command': command_type,
                'source': 'control_panel',
                'timestamp': self._get_timestamp()
            }
            logger.info(f"Quick command: {command_type}")
            self.on_send_command(command)
    
    def _get_timestamp(self) -> float:
        """Gets current timestamp."""
        import time
        return time.time()
    
    def _update_button_states(self):
        """Updates button states based on test status."""
        if self.test_active_var.get():
            # Test running - disable start, enable stop
            if self.start_button:
                self.start_button.config(state=tk.DISABLED)
            if self.stop_button:
                self.stop_button.config(state=tk.NORMAL)
        else:
            # Test not running - enable start, disable stop
            if self.start_button:
                self.start_button.config(state=tk.NORMAL)
            if self.stop_button:
                self.stop_button.config(state=tk.DISABLED)
    
    # =================================================================
    # External Interface Methods (called by presenter)
    # =================================================================
    
    def set_callbacks(self, callbacks: Dict[str, Callable]):
        """Sets callback functions for presenter communication."""
        self.on_start_test = callbacks.get('on_start_test')
        self.on_stop_test = callbacks.get('on_stop_test')
        self.on_emergency_stop = callbacks.get('on_emergency_stop')
        self.on_clear_buffer = callbacks.get('on_clear_buffer')
        self.on_send_command = callbacks.get('on_send_command')
        
        logger.info("Control panel callbacks configured")
    
    def set_test_active(self, active: bool):
        """Updates test active state and button states."""
        self.test_active_var.set(active)
        self._update_button_states()
        
        if active:
            logger.info("Test started - UI updated")
        else:
            logger.info("Test stopped - UI updated")
    
    def set_test_parameters(self, position: str = None, vehicle: str = None, duration: float = None):
        """Updates test parameters from external source."""
        if position:
            self.position_var.set(position)
        if vehicle:
            self.vehicle_var.set(vehicle)
        if duration:
            self.test_duration_var.set(str(duration))
        
        logger.debug(f"Test parameters updated: pos={position}, veh={vehicle}, dur={duration}")
    
    def get_test_parameters(self) -> Dict[str, Any]:
        """Returns current test parameters."""
        return {
            'position': self.position_var.get(),
            'vehicle_type': self.vehicle_var.get(),
            'duration': float(self.test_duration_var.get() or 30),
            'test_active': self.test_active_var.get()
        }
    
    def enable_controls(self, enabled: bool = True):
        """Enables or disables all controls."""
        state = tk.NORMAL if enabled else tk.DISABLED
        
        for widget in [self.position_combo, self.vehicle_combo, self.duration_entry]:
            if widget:
                widget.config(state=state if state == tk.NORMAL else "readonly")
        
        # Emergency button always enabled
        # Other buttons handled by _update_button_states()
        self._update_button_states()
        
        logger.info(f"Controls {'enabled' if enabled else 'disabled'}")
