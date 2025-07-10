"""
Discovery Dialog View for MQTT Broker Discovery.

Responsibility: UI for intelligent broker discovery, network scanning, and broker selection.
No business logic - only UI and result presentation.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable, Dict, Any, List
import logging
import threading
import time

logger = logging.getLogger(__name__)


class DiscoveryDialog:
    """
    Dialog for intelligent MQTT broker discovery.
    
    Features:
    - Intelligent suspension-specific broker discovery
    - Network scanning for MQTT brokers
    - Manual IP entry and testing
    - Broker confidence scoring
    - Topic analysis display
    """
    
    def __init__(self, parent: tk.Widget):
        self.parent = parent
        self.result = None
        self.discovery_running = False
        
        # Callbacks for discovery operations (injected by presenter)
        self.on_intelligent_discovery: Optional[Callable] = None
        self.on_network_scan: Optional[Callable] = None
        self.on_test_broker: Optional[Callable] = None
        self.on_analyze_topics: Optional[Callable] = None
        
        # UI Variables
        self.manual_ip_var = tk.StringVar(value="192.168.0.249")
        self.discovery_status_var = tk.StringVar(value="Ready")
        self.selected_broker_var = tk.StringVar(value="")
        
        # Dialog window
        self.dialog = None
        
        # UI Components
        self.discovery_tree = None
        self.progress_bar = None
        self.manual_status_label = None
        self.topic_display = None
        self.confidence_meter = None
        
        # Discovery results
        self.discovered_brokers = []
        self.broker_details = {}
        
        logger.info("DiscoveryDialog initialized")
    
    def show(self) -> Optional[Dict[str, Any]]:
        """Shows the discovery dialog and returns selected broker."""
        self._create_dialog()
        self._setup_dialog_ui()
        self._center_dialog()
        
        # Start initial discovery
        self._start_intelligent_discovery()
        
        # Wait for dialog to close
        self.dialog.wait_window()
        
        return self.result
    
    def _create_dialog(self):
        """Creates the dialog window."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("🎯 Intelligent Suspension Broker Discovery")
        self.dialog.geometry("900x700")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        # Make dialog resizable
        self.dialog.resizable(True, True)
    
    def _setup_dialog_ui(self):
        """Creates the complete dialog UI."""
        # Main container with padding
        main_frame = ttk.Frame(self.dialog, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header section
        self._setup_header(main_frame)
        
        # Discovery methods notebook
        self._setup_discovery_notebook(main_frame)
        
        # Status and progress section
        self._setup_status_section(main_frame)
        
        # Button section
        self._setup_button_section(main_frame)
    
    def _setup_header(self, parent):
        """Creates header section with info."""
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Title
        title_label = ttk.Label(
            header_frame, 
            text="🎯 Intelligent Suspension-Specific MQTT Broker Discovery",
            font=("TkDefaultFont", 14, "bold")
        )
        title_label.pack()
        
        # Subtitle
        subtitle_label = ttk.Label(
            header_frame,
            text="Analyzes MQTT brokers for suspension-specific topics with confidence scoring",
            font=("TkDefaultFont", 10)
        )
        subtitle_label.pack(pady=(5, 0))
        
        # Info box
        info_frame = ttk.LabelFrame(header_frame, text="ℹ️ How it works", padding="10")
        info_frame.pack(fill=tk.X, pady=(10, 0))
        
        info_text = (
            "🥇 Golden Topic: 'suspension/measurements/processed' = 95% confidence\n"
            "📊 Topic Analysis: Scans for suspension-related MQTT topics\n"
            "🔍 Network Scan: Searches for active MQTT brokers (port 1883)\n"
            "⚡ Smart Scoring: Ranks brokers by suspension topic relevance"
        )
        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack(anchor=tk.W)
    
    def _setup_discovery_notebook(self, parent):
        """Creates notebook with discovery methods."""
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Intelligent Discovery Tab
        self._setup_intelligent_tab(notebook)
        
        # Network Scan Tab
        self._setup_network_tab(notebook)
        
        # Manual Entry Tab
        self._setup_manual_tab(notebook)
        
        # Results Analysis Tab
        self._setup_analysis_tab(notebook)
    
    def _setup_intelligent_tab(self, notebook):
        """Creates intelligent discovery tab."""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="🎯 Intelligent Discovery")
        
        # Description
        desc_frame = ttk.LabelFrame(frame, text="📋 Intelligent Analysis", padding="10")
        desc_frame.pack(fill=tk.X, pady=(0, 10))
        
        desc_text = (
            "Automatically discovers and analyzes MQTT brokers for suspension testing compatibility.\n"
            "Scans network and evaluates topic relevance with confidence scoring."
        )
        ttk.Label(desc_frame, text=desc_text, justify=tk.LEFT).pack(anchor=tk.W)
        
        # Control buttons
        control_frame = ttk.Frame(desc_frame)
        control_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(control_frame, text="🚀 Start Intelligent Discovery", 
                  command=self._start_intelligent_discovery,
                  style="Accent.TButton").pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(control_frame, text="🔄 Refresh", 
                  command=self._refresh_discovery).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(control_frame, text="⚙️ Advanced Settings", 
                  command=self._show_advanced_settings).pack(side=tk.LEFT)
        
        # Results tree
        results_frame = ttk.LabelFrame(frame, text="🔍 Discovered Brokers", padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # Tree with columns
        columns = ("ip", "confidence", "topics", "latency", "status")
        self.discovery_tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=8)
        
        # Column configuration
        self.discovery_tree.heading("ip", text="IP Address")
        self.discovery_tree.heading("confidence", text="Confidence")
        self.discovery_tree.heading("topics", text="Suspension Topics")
        self.discovery_tree.heading("latency", text="Latency")
        self.discovery_tree.heading("status", text="Status")
        
        self.discovery_tree.column("ip", width=120)
        self.discovery_tree.column("confidence", width=100)
        self.discovery_tree.column("topics", width=150)
        self.discovery_tree.column("latency", width=80)
        self.discovery_tree.column("status", width=100)
        
        # Scrollbar for tree
        tree_scroll = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.discovery_tree.yview)
        self.discovery_tree.configure(yscrollcommand=tree_scroll.set)
        
        self.discovery_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Tree selection callback
        self.discovery_tree.bind("<<TreeviewSelect>>", self._on_broker_select)
        self.discovery_tree.bind("<Double-1>", self._on_broker_double_click)
    
    def _setup_network_tab(self, notebook):
        """Creates network scanning tab."""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="🔍 Network Scan")
        
        # Scan configuration
        config_frame = ttk.LabelFrame(frame, text="📡 Scan Configuration", padding="10")
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        config_grid = ttk.Frame(config_frame)
        config_grid.pack(fill=tk.X)
        
        # IP Range
        ttk.Label(config_grid, text="IP Range:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.ip_range_var = tk.StringVar(value="192.168.0.1-254")
        ttk.Entry(config_grid, textvariable=self.ip_range_var, width=20).grid(row=0, column=1, padx=(0, 20))
        
        # Port
        ttk.Label(config_grid, text="Port:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        self.port_var = tk.StringVar(value="1883")
        ttk.Entry(config_grid, textvariable=self.port_var, width=8).grid(row=0, column=3, padx=(0, 20))
        
        # Timeout
        ttk.Label(config_grid, text="Timeout (s):").grid(row=0, column=4, sticky=tk.W, padx=(0, 10))
        self.timeout_var = tk.StringVar(value="2")
        ttk.Entry(config_grid, textvariable=self.timeout_var, width=8).grid(row=0, column=5)
        
        # Scan controls
        scan_frame = ttk.Frame(config_frame)
        scan_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(scan_frame, text="🔍 Start Network Scan", 
                  command=self._start_network_scan).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(scan_frame, text="⏹️ Stop Scan", 
                  command=self._stop_scan).pack(side=tk.LEFT, padx=(0, 10))
        
        self.scan_progress = ttk.Progressbar(scan_frame, mode='indeterminate')
        self.scan_progress.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(20, 0))
        
        # Scan results
        scan_results_frame = ttk.LabelFrame(frame, text="📊 Scan Results", padding="10")
        scan_results_frame.pack(fill=tk.BOTH, expand=True)
        
        # Results text area
        self.scan_results_text = tk.Text(scan_results_frame, height=15, font=("Courier", 9))
        scan_scroll = ttk.Scrollbar(scan_results_frame, orient=tk.VERTICAL, command=self.scan_results_text.yview)
        self.scan_results_text.configure(yscrollcommand=scan_scroll.set)
        
        self.scan_results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scan_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _setup_manual_tab(self, notebook):
        """Creates manual entry tab."""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="✏️ Manual Entry")
        
        # Manual input section
        manual_frame = ttk.LabelFrame(frame, text="🖊️ Manual Broker Configuration", padding="15")
        manual_frame.pack(fill=tk.X, pady=(0, 10))
        
        # IP Entry
        ip_frame = ttk.Frame(manual_frame)
        ip_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(ip_frame, text="MQTT Broker IP:", 
                 font=("TkDefaultFont", 10, "bold")).pack(side=tk.LEFT)
        
        ip_entry = ttk.Entry(ip_frame, textvariable=self.manual_ip_var, width=20, font=("TkDefaultFont", 12))
        ip_entry.pack(side=tk.LEFT, padx=(10, 20))
        
        ttk.Button(ip_frame, text="🧪 Test Connection", 
                  command=self._test_manual_broker).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(ip_frame, text="✅ Use This Broker", 
                  command=self._use_manual_broker).pack(side=tk.LEFT)
        
        # Status display
        self.manual_status_label = ttk.Label(manual_frame, text="", font=("TkDefaultFont", 10))
        self.manual_status_label.pack(pady=(10, 0))
        
        # Predefined brokers
        predefined_frame = ttk.LabelFrame(frame, text="📋 Common Broker IPs", padding="10")
        predefined_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Predefined IP buttons
        ip_buttons_frame = ttk.Frame(predefined_frame)
        ip_buttons_frame.pack(fill=tk.X)
        
        common_ips = ["192.168.0.249", "192.168.1.100", "192.168.178.100", "localhost"]
        for i, ip in enumerate(common_ips):
            ttk.Button(ip_buttons_frame, text=ip, 
                      command=lambda x=ip: self.manual_ip_var.set(x),
                      width=15).grid(row=i//2, column=i%2, padx=5, pady=2, sticky="ew")
        
        # Configure grid weights
        ip_buttons_frame.grid_columnconfigure(0, weight=1)
        ip_buttons_frame.grid_columnconfigure(1, weight=1)
        
        # Tips section
        tips_frame = ttk.LabelFrame(frame, text="💡 Tips", padding="10")
        tips_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        tips_text = (
            "🔍 Finding your broker IP:\n"
            "• Check your router admin panel for connected devices\n"
            "• Look for Raspberry Pi, IoT devices, or computers running MQTT\n"
            "• Try common IoT IP ranges: 192.168.0.x, 192.168.1.x\n\n"
            "🧪 Testing connection:\n"
            "• Tests basic MQTT connectivity on port 1883\n"
            "• Checks for suspension-specific topics\n"
            "• Shows latency and broker info\n\n"
            "⚡ Quick selection:\n"
            "• Click predefined IPs to auto-fill the entry field\n"
            "• Double-click in discovery results to select broker"
        )
        
        ttk.Label(tips_frame, text=tips_text, justify=tk.LEFT, font=("TkDefaultFont", 9)).pack(anchor=tk.W)
    
    def _setup_analysis_tab(self, notebook):
        """Creates broker analysis tab."""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="📊 Analysis")
        
        # Selected broker info
        broker_frame = ttk.LabelFrame(frame, text="🎯 Selected Broker Details", padding="10")
        broker_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.broker_info_text = tk.Text(broker_frame, height=6, font=("Courier", 9))
        broker_info_scroll = ttk.Scrollbar(broker_frame, orient=tk.VERTICAL, command=self.broker_info_text.yview)
        self.broker_info_text.configure(yscrollcommand=broker_info_scroll.set)
        
        self.broker_info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        broker_info_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Topic analysis
        topic_frame = ttk.LabelFrame(frame, text="📋 Topic Analysis", padding="10")
        topic_frame.pack(fill=tk.BOTH, expand=True)
        
        # Topic tree
        topic_columns = ("topic", "confidence", "message_count", "last_seen")
        self.topic_tree = ttk.Treeview(topic_frame, columns=topic_columns, show="headings", height=10)
        
        self.topic_tree.heading("topic", text="Topic")
        self.topic_tree.heading("confidence", text="Confidence")
        self.topic_tree.heading("message_count", text="Messages")
        self.topic_tree.heading("last_seen", text="Last Seen")
        
        self.topic_tree.column("topic", width=300)
        self.topic_tree.column("confidence", width=100)
        self.topic_tree.column("message_count", width=100)
        self.topic_tree.column("last_seen", width=150)
        
        topic_scroll = ttk.Scrollbar(topic_frame, orient=tk.VERTICAL, command=self.topic_tree.yview)
        self.topic_tree.configure(yscrollcommand=topic_scroll.set)
        
        self.topic_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        topic_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _setup_status_section(self, parent):
        """Creates status and progress section."""
        status_frame = ttk.LabelFrame(parent, text="📊 Discovery Status", padding="10")
        status_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Status grid
        status_grid = ttk.Frame(status_frame)
        status_grid.pack(fill=tk.X)
        
        # Status label
        ttk.Label(status_grid, text="Status:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.status_label = ttk.Label(status_grid, textvariable=self.discovery_status_var, 
                                     font=("TkDefaultFont", 10, "bold"))
        self.status_label.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(status_grid, length=200, mode='indeterminate')
        self.progress_bar.grid(row=0, column=2, padx=(20, 0))
        
        # Selected broker display
        selected_frame = ttk.Frame(status_frame)
        selected_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(selected_frame, text="Selected Broker:", 
                 font=("TkDefaultFont", 10, "bold")).pack(side=tk.LEFT)
        
        self.selected_label = ttk.Label(selected_frame, textvariable=self.selected_broker_var,
                                       font=("TkDefaultFont", 11, "bold"), foreground='blue')
        self.selected_label.pack(side=tk.LEFT, padx=(10, 0))
    
    def _setup_button_section(self, parent):
        """Creates dialog action buttons."""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Action buttons
        ttk.Button(button_frame, text="✅ Use Selected Broker", 
                  command=self._confirm_selection,
                  style="Accent.TButton").pack(side=tk.RIGHT, padx=(10, 0))
        
        ttk.Button(button_frame, text="❌ Cancel", 
                  command=self._on_cancel).pack(side=tk.RIGHT)
        
        ttk.Button(button_frame, text="ℹ️ Help", 
                  command=self._show_help).pack(side=tk.LEFT)
    
    def _center_dialog(self):
        """Centers the dialog on screen."""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
    
    # =================================================================
    # Discovery Methods (delegated to presenter)
    # =================================================================
    
    def _start_intelligent_discovery(self):
        """Starts intelligent broker discovery."""
        if self.discovery_running:
            return
        
        self.discovery_running = True
        self.discovery_status_var.set("🔍 Starting intelligent discovery...")
        self.progress_bar.start()
        
        # Clear previous results
        if self.discovery_tree:
            for item in self.discovery_tree.get_children():
                self.discovery_tree.delete(item)
        
        # Delegate to presenter
        if self.on_intelligent_discovery:
            threading.Thread(target=self._run_intelligent_discovery, daemon=True).start()
        else:
            self._discovery_complete([])
    
    def _run_intelligent_discovery(self):
        """Runs intelligent discovery in background thread."""
        try:
            # Call presenter method
            results = self.on_intelligent_discovery() if self.on_intelligent_discovery else []
            
            # Update UI in main thread
            self.dialog.after(0, self._discovery_complete, results)
            
        except Exception as e:
            logger.error(f"Intelligent discovery error: {e}")
            self.dialog.after(0, self._discovery_error, str(e))
    
    def _discovery_complete(self, results: List[Dict[str, Any]]):
        """Handles completed discovery."""
        self.discovery_running = False
        self.progress_bar.stop()
        
        self.discovered_brokers = results
        self.discovery_status_var.set(f"✅ Discovery complete - {len(results)} brokers found")
        
        # Populate tree
        self._populate_discovery_tree(results)
        
        # Auto-select best broker
        if results:
            best_broker = max(results, key=lambda x: x.get('confidence', 0))
            self._select_broker(best_broker)
    
    def _discovery_error(self, error: str):
        """Handles discovery error."""
        self.discovery_running = False
        self.progress_bar.stop()
        self.discovery_status_var.set(f"❌ Discovery failed: {error}")
    
    def _populate_discovery_tree(self, brokers: List[Dict[str, Any]]):
        """Populates the discovery tree with broker results."""
        if not self.discovery_tree:
            return
        
        # Clear existing items
        for item in self.discovery_tree.get_children():
            self.discovery_tree.delete(item)
        
        # Add broker entries
        for broker in brokers:
            ip = broker.get('ip', 'Unknown')
            confidence = f"{broker.get('confidence', 0)*100:.0f}%"
            topics = str(len(broker.get('suspension_topics', [])))
            latency = f"{broker.get('latency', 0)*1000:.0f}ms"
            status = broker.get('status', 'Unknown')
            
            # Color coding based on confidence
            tags = []
            if broker.get('confidence', 0) >= 0.9:
                tags = ['high_confidence']
            elif broker.get('confidence', 0) >= 0.5:
                tags = ['medium_confidence']
            else:
                tags = ['low_confidence']
            
            self.discovery_tree.insert('', 'end', values=(ip, confidence, topics, latency, status), tags=tags)
        
        # Configure tag colors
        self.discovery_tree.tag_configure('high_confidence', background='lightgreen')
        self.discovery_tree.tag_configure('medium_confidence', background='lightyellow')
        self.discovery_tree.tag_configure('low_confidence', background='lightcoral')
    
    # =================================================================
    # Event Handlers
    # =================================================================
    
    def _on_broker_select(self, event):
        """Handles broker selection in tree."""
        if not self.discovery_tree:
            return
        
        selection = self.discovery_tree.selection()
        if selection:
            item = selection[0]
            values = self.discovery_tree.item(item, 'values')
            if values:
                ip = values[0]
                
                # Find broker details
                selected_broker = None
                for broker in self.discovered_brokers:
                    if broker.get('ip') == ip:
                        selected_broker = broker
                        break
                
                if selected_broker:
                    self._select_broker(selected_broker)
    
    def _on_broker_double_click(self, event):
        """Handles double-click on broker (auto-select)."""
        self._on_broker_select(event)
        self._confirm_selection()
    
    def _select_broker(self, broker: Dict[str, Any]):
        """Selects a broker and updates UI."""
        ip = broker.get('ip', 'Unknown')
        confidence = broker.get('confidence', 0)
        
        self.selected_broker_var.set(f"{ip} ({confidence*100:.0f}% confidence)")
        
        # Update broker details
        if hasattr(self, 'broker_info_text'):
            self.broker_info_text.delete('1.0', tk.END)
            
            info_text = f"IP Address: {ip}\n"
            info_text += f"Confidence: {confidence*100:.1f}%\n"
            info_text += f"Latency: {broker.get('latency', 0)*1000:.0f}ms\n"
            info_text += f"Status: {broker.get('status', 'Unknown')}\n"
            info_text += f"Suspension Topics: {len(broker.get('suspension_topics', []))}\n"
            info_text += f"Method: {broker.get('discovery_method', 'Unknown')}\n"
            
            self.broker_info_text.insert('1.0', info_text)
        
        # Update topic analysis
        self._update_topic_analysis(broker.get('suspension_topics', []))
        
        # Store for result
        self.selected_broker = broker
    
    def _update_topic_analysis(self, topics: List[Dict[str, Any]]):
        """Updates topic analysis display."""
        if not hasattr(self, 'topic_tree') or not self.topic_tree:
            return
        
        # Clear existing items
        for item in self.topic_tree.get_children():
            self.topic_tree.delete(item)
        
        # Add topic entries
        for topic_info in topics:
            topic = topic_info.get('topic', 'Unknown')
            confidence = f"{topic_info.get('confidence', 0)*100:.0f}%"
            count = str(topic_info.get('message_count', 0))
            last_seen = topic_info.get('last_seen', 'Never')
            
            self.topic_tree.insert('', 'end', values=(topic, confidence, count, last_seen))
    
    def _test_manual_broker(self):
        """Tests manually entered broker."""
        ip = self.manual_ip_var.get().strip()
        if not ip:
            self._update_manual_status("❌ Please enter an IP address", 'red')
            return
        
        self._update_manual_status("🧪 Testing connection...", 'orange')
        
        # Delegate to presenter
        if self.on_test_broker:
            threading.Thread(target=self._run_manual_test, args=(ip,), daemon=True).start()
        else:
            self._update_manual_status("❌ Test function not available", 'red')
    
    def _run_manual_test(self, ip: str):
        """Runs manual broker test in background."""
        try:
            result = self.on_test_broker(ip) if self.on_test_broker else None
            self.dialog.after(0, self._manual_test_complete, result)
        except Exception as e:
            self.dialog.after(0, self._manual_test_error, str(e))
    
    def _manual_test_complete(self, result: Dict[str, Any]):
        """Handles completed manual test."""
        if result and result.get('success'):
            confidence = result.get('confidence', 0)
            latency = result.get('latency', 0)
            topics = len(result.get('suspension_topics', []))
            
            status_text = f"✅ Connected! Confidence: {confidence*100:.0f}%, {topics} topics, {latency*1000:.0f}ms"
            self._update_manual_status(status_text, 'green')
            
            # Store for potential selection
            self.manual_broker_result = result
        else:
            error = result.get('error', 'Unknown error') if result else 'No response'
            self._update_manual_status(f"❌ Connection failed: {error}", 'red')
    
    def _manual_test_error(self, error: str):
        """Handles manual test error."""
        self._update_manual_status(f"❌ Test error: {error}", 'red')
    
    def _update_manual_status(self, text: str, color: str):
        """Updates manual test status."""
        if self.manual_status_label:
            self.manual_status_label.config(text=text, foreground=color)
    
    def _use_manual_broker(self):
        """Uses manually entered broker."""
        ip = self.manual_ip_var.get().strip()
        if not ip:
            self._update_manual_status("❌ Please enter an IP address", 'red')
            return
        
        # Create broker result
        manual_broker = {
            'ip': ip,
            'confidence': getattr(self, 'manual_broker_result', {}).get('confidence', 0.5),
            'method': 'manual_entry',
            'timestamp': time.time()
        }
        
        self._select_broker(manual_broker)
        self._update_manual_status("✅ Manual broker selected", 'green')
    
    def _confirm_selection(self):
        """Confirms broker selection and closes dialog."""
        if hasattr(self, 'selected_broker') and self.selected_broker:
            self.result = self.selected_broker
            self.dialog.destroy()
        else:
            self.discovery_status_var.set("❌ Please select a broker first")
    
    def _on_cancel(self):
        """Handles dialog cancellation."""
        self.result = None
        if self.dialog:
            self.dialog.destroy()
    
    # =================================================================
    # Additional Methods
    # =================================================================
    
    def _refresh_discovery(self):
        """Refreshes the discovery process."""
        self._start_intelligent_discovery()
    
    def _start_network_scan(self):
        """Starts network scanning."""
        self.scan_progress.start()
        # Implementation delegated to presenter
        if self.on_network_scan:
            threading.Thread(target=self._run_network_scan, daemon=True).start()
    
    def _run_network_scan(self):
        """Runs network scan in background."""
        # Implementation would be delegated to presenter
        pass
    
    def _stop_scan(self):
        """Stops current scan."""
        self.scan_progress.stop()
    
    def _show_advanced_settings(self):
        """Shows advanced discovery settings."""
        # Placeholder for advanced settings dialog
        pass
    
    def _show_help(self):
        """Shows help dialog."""
        help_text = """
🎯 Intelligent MQTT Broker Discovery Help

This tool helps you find and configure MQTT brokers for suspension testing.

Discovery Methods:
• Intelligent: Automatically scans and analyzes brokers for suspension compatibility
• Network Scan: Searches your network for MQTT brokers on port 1883
• Manual: Enter a known IP address directly

Confidence Scoring:
• 95%: Broker has the golden topic 'suspension/measurements/processed'
• 80%+: Multiple suspension-related topics found
• 60%+: Some relevant topics detected
• <60%: Basic MQTT broker, may not be optimal

Tips:
• Green highlights indicate high-confidence brokers
• Double-click a broker to select it immediately
• The system will automatically use the best available broker
        """
        
        help_dialog = tk.Toplevel(self.dialog)
        help_dialog.title("📚 Discovery Help")
        help_dialog.geometry("600x400")
        help_dialog.transient(self.dialog)
        
        text_widget = tk.Text(help_dialog, wrap=tk.WORD, padx=15, pady=15)
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert('1.0', help_text)
        text_widget.config(state=tk.DISABLED)
        
        ttk.Button(help_dialog, text="Close", command=help_dialog.destroy).pack(pady=10)
    
    # =================================================================
    # External Interface (for presenter)
    # =================================================================
    
    def set_callbacks(self, callbacks: Dict[str, Callable]):
        """Sets callback functions for discovery operations."""
        self.on_intelligent_discovery = callbacks.get('on_intelligent_discovery')
        self.on_network_scan = callbacks.get('on_network_scan')
        self.on_test_broker = callbacks.get('on_test_broker')
        self.on_analyze_topics = callbacks.get('on_analyze_topics')
        
        logger.info("Discovery dialog callbacks configured")
