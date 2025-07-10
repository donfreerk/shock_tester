"""
Status Bar View for EGEA Suspension Tester.

Responsibility: Display system status, connection info, and real-time metrics.
No business logic - only status display and formatting.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable, Dict, Any
import logging
import time

logger = logging.getLogger(__name__)


class StatusBar:
    """
    Status bar for system information display.
    
    Features:
    - MQTT connection status
    - Data counter and performance metrics
    - EGEA analysis status
    - System health indicators
    - Real-time updates
    """
    
    def __init__(self, parent: tk.Widget):
        self.parent = parent
        
        # Callbacks to presenter (for actions like reconnect)
        self.on_mqtt_reconnect: Optional[Callable] = None
        self.on_discovery_open: Optional[Callable] = None
        self.on_status_details: Optional[Callable] = None
        
        # Status variables
        self.mqtt_broker_var = tk.StringVar(value="Detecting...")
        self.mqtt_status_var = tk.StringVar(value="Disconnected")
        self.data_count_var = tk.StringVar(value="0")
        self.data_rate_var = tk.StringVar(value="0.0/s")
        self.egea_status_var = tk.StringVar(value="Ready")
        self.egea_phase_var = tk.StringVar(value="φ: --°")
        self.egea_quality_var = tk.StringVar(value="Q: --%")
        self.performance_var = tk.StringVar(value="Performance: OK")
        
        # Status colors
        self.status_colors = {
            'connected': '#28a745',    # Green
            'connecting': '#ffc107',   # Yellow
            'disconnected': '#dc3545', # Red
            'unknown': '#6c757d'       # Gray
        }
        
        # UI Components
        self.mqtt_status_label = None
        self.mqtt_broker_label = None
        self.data_labels = {}
        self.egea_labels = {}
        self.performance_label = None
        
        self._setup_ui()
        
        logger.info("StatusBar initialized")
    
    def _setup_ui(self):
        """Creates the status bar UI."""
        # Main status frame
        status_frame = ttk.LabelFrame(self.parent, text="📊 System Status", padding="10")
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Grid layout for organized status display
        status_grid = ttk.Frame(status_frame)
        status_grid.pack(fill=tk.X)
        
        # Configure grid columns
        for i in range(6):
            status_grid.grid_columnconfigure(i, weight=1)
        
        # MQTT Status Section
        self._setup_mqtt_status(status_grid)
        
        # Data Status Section
        self._setup_data_status(status_grid)
        
        # EGEA Status Section
        self._setup_egea_status(status_grid)
        
        # Performance Section
        self._setup_performance_status(status_grid)
    
    def _setup_mqtt_status(self, parent):
        """Creates MQTT connection status section."""
        # MQTT Section Header
        mqtt_frame = ttk.LabelFrame(parent, text="🌐 MQTT Connection", padding="5")
        mqtt_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=(0, 10))
        
        # Broker info
        broker_frame = ttk.Frame(mqtt_frame)
        broker_frame.pack(fill=tk.X)
        
        ttk.Label(broker_frame, text="Broker:", 
                 font=("TkDefaultFont", 9, "bold")).pack(side=tk.LEFT)
        
        self.mqtt_broker_label = ttk.Label(
            broker_frame, textvariable=self.mqtt_broker_var,
            font=("TkDefaultFont", 9), foreground='blue'
        )
        self.mqtt_broker_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Status info
        status_frame = ttk.Frame(mqtt_frame)
        status_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT)
        
        self.mqtt_status_label = ttk.Label(
            status_frame, textvariable=self.mqtt_status_var,
            font=("TkDefaultFont", 9, "bold")
        )
        self.mqtt_status_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Action buttons
        action_frame = ttk.Frame(mqtt_frame)
        action_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(action_frame, text="🔄", 
                  command=self._on_reconnect_click, width=3).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(action_frame, text="🎯", 
                  command=self._on_discovery_click, width=3).pack(side=tk.LEFT)
    
    def _setup_data_status(self, parent):
        """Creates data flow status section."""
        data_frame = ttk.LabelFrame(parent, text="📈 Data Flow", padding="5")
        data_frame.grid(row=0, column=2, columnspan=2, sticky="ew", padx=(0, 10))
        
        # Data counter
        count_frame = ttk.Frame(data_frame)
        count_frame.pack(fill=tk.X)
        
        ttk.Label(count_frame, text="Count:").pack(side=tk.LEFT)
        self.data_labels['count'] = ttk.Label(
            count_frame, textvariable=self.data_count_var,
            font=("TkDefaultFont", 9, "bold"), foreground='green'
        )
        self.data_labels['count'].pack(side=tk.LEFT, padx=(5, 0))
        
        # Data rate
        rate_frame = ttk.Frame(data_frame)
        rate_frame.pack(fill=tk.X, pady=(3, 0))
        
        ttk.Label(rate_frame, text="Rate:").pack(side=tk.LEFT)
        self.data_labels['rate'] = ttk.Label(
            rate_frame, textvariable=self.data_rate_var,
            font=("TkDefaultFont", 9)
        )
        self.data_labels['rate'].pack(side=tk.LEFT, padx=(5, 0))
        
        # Buffer status
        buffer_frame = ttk.Frame(data_frame)
        buffer_frame.pack(fill=tk.X, pady=(3, 0))
        
        self.buffer_progress = ttk.Progressbar(
            buffer_frame, length=100, mode='determinate'
        )
        self.buffer_progress.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.data_labels['buffer'] = ttk.Label(buffer_frame, text="0%", width=4)
        self.data_labels['buffer'].pack(side=tk.RIGHT)
    
    def _setup_egea_status(self, parent):
        """Creates EGEA analysis status section."""
        egea_frame = ttk.LabelFrame(parent, text="🎯 EGEA Analysis", padding="5")
        egea_frame.grid(row=0, column=4, sticky="ew", padx=(0, 10))
        
        # EGEA status
        status_frame = ttk.Frame(egea_frame)
        status_frame.pack(fill=tk.X)
        
        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT)
        self.egea_labels['status'] = ttk.Label(
            status_frame, textvariable=self.egea_status_var,
            font=("TkDefaultFont", 9, "bold")
        )
        self.egea_labels['status'].pack(side=tk.LEFT, padx=(5, 0))
        
        # Phase shift
        phase_frame = ttk.Frame(egea_frame)
        phase_frame.pack(fill=tk.X, pady=(3, 0))
        
        self.egea_labels['phase'] = ttk.Label(
            phase_frame, textvariable=self.egea_phase_var,
            font=("TkDefaultFont", 9, "bold"), foreground='navy'
        )
        self.egea_labels['phase'].pack(side=tk.LEFT)
        
        # Quality indicator
        quality_frame = ttk.Frame(egea_frame)
        quality_frame.pack(fill=tk.X, pady=(3, 0))
        
        self.egea_labels['quality'] = ttk.Label(
            quality_frame, textvariable=self.egea_quality_var,
            font=("TkDefaultFont", 9)
        )
        self.egea_labels['quality'].pack(side=tk.LEFT)
        
        # Threshold indicator
        threshold_frame = ttk.Frame(egea_frame)
        threshold_frame.pack(fill=tk.X, pady=(3, 0))
        
        ttk.Label(threshold_frame, text="Limit: 35°", 
                 font=("TkDefaultFont", 8), foreground='gray').pack()
    
    def _setup_performance_status(self, parent):
        """Creates performance metrics section."""
        perf_frame = ttk.LabelFrame(parent, text="⚡ Performance", padding="5")
        perf_frame.grid(row=0, column=5, sticky="ew")
        
        # Performance indicator
        self.performance_label = ttk.Label(
            perf_frame, textvariable=self.performance_var,
            font=("TkDefaultFont", 9)
        )
        self.performance_label.pack()
        
        # Detailed metrics button
        ttk.Button(perf_frame, text="Details", 
                  command=self._on_details_click, width=8).pack(pady=(5, 0))
    
    def _on_reconnect_click(self):
        """Handles MQTT reconnect button click."""
        if self.on_mqtt_reconnect:
            logger.info("MQTT reconnect requested from status bar")
            self.on_mqtt_reconnect()
    
    def _on_discovery_click(self):
        """Handles discovery button click."""
        if self.on_discovery_open:
            logger.info("Discovery dialog requested from status bar")
            self.on_discovery_open()
    
    def _on_details_click(self):
        """Handles performance details button click."""
        if self.on_status_details:
            logger.info("Status details requested")
            self.on_status_details()
    
    def _format_data_rate(self, rate: float) -> str:
        """Formats data rate for display."""
        if rate >= 1000:
            return f"{rate/1000:.1f}k/s"
        elif rate >= 1:
            return f"{rate:.1f}/s"
        else:
            return f"{rate:.2f}/s"
    
    def _format_performance_metrics(self, metrics: Dict[str, Any]) -> str:
        """Formats performance metrics for display."""
        if not metrics:
            return "Performance: OK"
        
        cpu = metrics.get('cpu_usage', 0)
        memory = metrics.get('memory_mb', 0)
        fps = metrics.get('fps', 0)
        
        if cpu > 80 or memory > 1000:
            return f"⚠️ High Load"
        elif fps > 0 and fps < 10:
            return f"⚠️ Low FPS"
        else:
            return f"✅ OK ({fps:.0f} FPS)"
    
    # =================================================================
    # External Interface Methods (called by presenter)
    # =================================================================
    
    def set_callbacks(self, callbacks: Dict[str, Callable]):
        """Sets callback functions for presenter communication."""
        self.on_mqtt_reconnect = callbacks.get('on_mqtt_reconnect')
        self.on_discovery_open = callbacks.get('on_discovery_open')
        self.on_status_details = callbacks.get('on_status_details')
        
        logger.info("Status bar callbacks configured")
    
    def update_mqtt_status(self, broker: str = None, status: str = None, connected: bool = None):
        """Updates MQTT connection status."""
        if broker:
            self.mqtt_broker_var.set(broker)
        
        if status:
            self.mqtt_status_var.set(status)
            
            # Update status label color
            if self.mqtt_status_label:
                if connected is True:
                    color = self.status_colors['connected']
                    status_text = f"✅ {status}"
                elif connected is False:
                    color = self.status_colors['disconnected'] 
                    status_text = f"❌ {status}"
                else:
                    color = self.status_colors['connecting']
                    status_text = f"🔄 {status}"
                
                self.mqtt_status_var.set(status_text)
                self.mqtt_status_label.config(foreground=color)
        
        logger.debug(f"MQTT status updated: {broker}, {status}, connected={connected}")
    
    def update_data_status(self, count: int = None, rate: float = None, buffer_usage: float = None):
        """Updates data flow status."""
        if count is not None:
            self.data_count_var.set(f"{count:,}")
        
        if rate is not None:
            formatted_rate = self._format_data_rate(rate)
            self.data_rate_var.set(formatted_rate)
            
            # Update rate label color based on performance
            if self.data_labels.get('rate'):
                if rate > 10:
                    color = 'green'
                elif rate > 1:
                    color = 'orange'
                else:
                    color = 'red'
                self.data_labels['rate'].config(foreground=color)
        
        if buffer_usage is not None:
            # Update progress bar
            if self.buffer_progress:
                self.buffer_progress['value'] = buffer_usage * 100
            
            # Update percentage label
            if self.data_labels.get('buffer'):
                self.data_labels['buffer'].config(text=f"{buffer_usage*100:.0f}%")
                
                # Color coding for buffer usage
                if buffer_usage > 0.9:
                    color = 'red'
                elif buffer_usage > 0.7:
                    color = 'orange'
                else:
                    color = 'green'
                self.data_labels['buffer'].config(foreground=color)
        
        logger.debug(f"Data status updated: count={count}, rate={rate}, buffer={buffer_usage}")
    
    def update_egea_status(self, status: str = None, phase_shift: float = None, 
                          quality: float = None, passing: bool = None):
        """Updates EGEA analysis status."""
        if status:
            self.egea_status_var.set(status)
            
            # Update status color
            if self.egea_labels.get('status'):
                if passing is True:
                    color = 'green'
                    status_text = f"✅ {status}"
                elif passing is False:
                    color = 'red'
                    status_text = f"❌ {status}"
                else:
                    color = 'blue'
                    status_text = f"🔄 {status}"
                
                self.egea_status_var.set(status_text)
                self.egea_labels['status'].config(foreground=color)
        
        if phase_shift is not None:
            phase_text = f"φ: {phase_shift:.1f}°"
            self.egea_phase_var.set(phase_text)
            
            # Color code based on EGEA threshold (35°)
            if self.egea_labels.get('phase'):
                if phase_shift >= 35:
                    color = 'green'
                elif phase_shift >= 30:
                    color = 'orange' 
                else:
                    color = 'red'
                self.egea_labels['phase'].config(foreground=color)
        
        if quality is not None:
            quality_text = f"Q: {quality:.0f}%"
            self.egea_quality_var.set(quality_text)
            
            # Color code quality
            if self.egea_labels.get('quality'):
                if quality >= 80:
                    color = 'green'
                elif quality >= 60:
                    color = 'orange'
                else:
                    color = 'red'
                self.egea_labels['quality'].config(foreground=color)
        
        logger.debug(f"EGEA status updated: {status}, φ={phase_shift}, Q={quality}, pass={passing}")
    
    def update_performance_status(self, metrics: Dict[str, Any] = None):
        """Updates performance metrics display."""
        if metrics:
            perf_text = self._format_performance_metrics(metrics)
            self.performance_var.set(perf_text)
            
            # Color code performance
            if self.performance_label:
                cpu = metrics.get('cpu_usage', 0)
                memory = metrics.get('memory_mb', 0)
                fps = metrics.get('fps', 30)
                
                if cpu > 80 or memory > 1000 or fps < 10:
                    color = 'red'
                elif cpu > 60 or memory > 500 or fps < 20:
                    color = 'orange'
                else:
                    color = 'green'
                
                self.performance_label.config(foreground=color)
        
        logger.debug(f"Performance status updated: {metrics}")
    
    def set_test_active(self, active: bool):
        """Updates UI for test active state."""
        if active:
            # Test running - more prominent data display
            if self.data_labels.get('count'):
                self.data_labels['count'].config(font=("TkDefaultFont", 10, "bold"))
        else:
            # Test not running - normal display
            if self.data_labels.get('count'):
                self.data_labels['count'].config(font=("TkDefaultFont", 9, "bold"))
    
    def get_current_status(self) -> Dict[str, Any]:
        """Returns current status information."""
        return {
            'mqtt': {
                'broker': self.mqtt_broker_var.get(),
                'status': self.mqtt_status_var.get()
            },
            'data': {
                'count': self.data_count_var.get(),
                'rate': self.data_rate_var.get()
            },
            'egea': {
                'status': self.egea_status_var.get(),
                'phase': self.egea_phase_var.get(),
                'quality': self.egea_quality_var.get()
            },
            'performance': self.performance_var.get(),
            'timestamp': time.time()
        }
