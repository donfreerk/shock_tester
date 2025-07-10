"""
Background Processor for EGEA Phase-Shift Calculations.

✅ KONSOLIDIERT: Nutzt zentrale suspension_core.egea Implementation

Responsibility: High-performance background processing using central EGEA algorithms.
Features: Threading, queue management, performance monitoring, central implementation wrapper.

MIGRATION STATUS: ✅ Consolidated to use suspension_core.egea.PhaseShiftProcessor
"""

import threading
import queue
import time
import logging
import numpy as np
from typing import Dict, Any, List, Optional, Callable
from collections import deque
from dataclasses import dataclass
import multiprocessing as mp

logger = logging.getLogger(__name__)

# Zentrale EGEA-Implementation importieren
try:
    from suspension_core.egea import EGEAPhaseShiftProcessor
    from suspension_core.config import ConfigManager
    CENTRAL_EGEA_AVAILABLE = True
    logger.info("✅ Zentrale EGEA PhaseShiftProcessor erfolgreich importiert")
except ImportError as e:
    CENTRAL_EGEA_AVAILABLE = False
    logger.error(f"❌ Zentrale EGEA PhaseShiftProcessor nicht verfügbar: {e}")
    logger.error("Installieren Sie suspension_core oder prüfen Sie PYTHONPATH")


@dataclass
class ProcessingTask:
    """Container for processing tasks."""
    task_id: str
    task_type: str
    data: Dict[str, Any]
    timestamp: float
    priority: int = 0  # 0 = highest priority
    
    def __lt__(self, other):
        """For priority queue ordering."""
        return self.priority < other.priority


@dataclass
class ProcessingResult:
    """Container for processing results."""
    task_id: str
    task_type: str
    result: Dict[str, Any]
    processing_time: float
    timestamp: float
    success: bool
    error: Optional[str] = None


class PhaseShiftProcessor:
    """
    GUI-optimized Phase-Shift processor wrapper for central EGEA implementation.
    
    Features:
    - Wraps central suspension_core.egea.EGEAPhaseShiftProcessor
    - GUI-compatible API and result formats
    - Performance monitoring and caching
    - Backwards-compatible with existing GUI code
    
    MIGRATION: ✅ All calculations delegated to central implementation
    """
    
    def __init__(self):
        """Initialize with central EGEA processor or fallback."""
        
        if not CENTRAL_EGEA_AVAILABLE:
            raise ImportError(
                "Zentrale EGEA PhaseShiftProcessor nicht verfügbar.\n"
                "Bitte installieren Sie suspension_core oder prüfen Sie PYTHONPATH:\n"
                "export PYTHONPATH=$PYTHONPATH:./common"
            )
        
        # Zentrale EGEA-Implementation
        self.egea_processor = EGEAPhaseShiftProcessor()
        
        # GUI-spezifische Parameter (für Kompatibilität)
        self.min_freq = 6.0
        self.max_freq = 25.0
        self.phase_threshold = 35.0
        
        # Performance settings
        self.use_vectorized = True
        self.cache_fft = True
        self.max_cache_size = 100
        
        # GUI-spezifische Caching (für Performance)
        self._result_cache = {}
        
        # Performance tracking
        self.processing_times = deque(maxlen=1000)
        self.cache_hits = 0
        self.cache_misses = 0
        
        logger.info("✅ GUI PhaseShiftProcessor initialisiert mit zentraler EGEA-Implementation")
    
    def calculate_phase_shift(self, platform_data: np.ndarray, force_data: np.ndarray, 
                            time_data: np.ndarray, static_weight: float) -> Dict[str, Any]:
        """
        Calculate phase shift using central EGEA implementation.
        
        KOMPATIBLE API: Behält GUI-kompatible API bei, delegiert an zentrale Implementation.
        
        Args:
            platform_data: Platform position array
            force_data: Force measurement array
            time_data: Time array
            static_weight: Static weight value
            
        Returns:
            Dictionary with phase shift results (GUI-compatible format)
        """
        start_time = time.perf_counter()
        
        try:
            # Input validation
            if not self._validate_inputs(platform_data, force_data, time_data):
                return self._create_error_result("Invalid input data")
            
            # Generate cache key für GUI-Performance
            cache_key = self._generate_cache_key(platform_data, force_data, static_weight)
            
            # Check cache first
            if self.cache_fft and cache_key in self._result_cache:
                self.cache_hits += 1
                logger.debug("Phase shift result from GUI cache")
                return self._result_cache[cache_key]
            
            self.cache_misses += 1
            
            # ✅ ZENTRALE EGEA-IMPLEMENTATION VERWENDEN
            egea_result = self.egea_processor.calculate_phase_shift_advanced(
                platform_position=platform_data,
                tire_force=force_data, 
                time_array=time_data,
                static_weight=static_weight
            )
            
            # Konvertierung zu GUI-kompatiblem Format
            gui_result = self._convert_egea_to_gui_format(egea_result)
            
            # Cache result für GUI-Performance
            if self.cache_fft and len(self._result_cache) < self.max_cache_size:
                self._result_cache[cache_key] = gui_result
            
            # Performance tracking
            processing_time = time.perf_counter() - start_time
            self.processing_times.append(processing_time)
            gui_result['processing_time'] = processing_time
            
            logger.debug(f"✅ Phase-Shift berechnet mit zentraler EGEA-Implementation: "
                        f"{gui_result.get('min_phase_shift', 0):.1f}° in {processing_time:.3f}s")
            
            return gui_result
            
        except Exception as e:
            logger.error(f"❌ Phase shift calculation error (zentrale Implementation): {e}")
            return self._create_error_result(str(e))
    
    def _convert_egea_to_gui_format(self, egea_result) -> Dict[str, Any]:
        """
        Konvertiert EGEA-Result zu GUI-kompatiblem Format.
        
        Args:
            egea_result: PhaseShiftResult von zentraler EGEA-Implementation
            
        Returns:
            GUI-kompatibles Dictionary
        """
        try:
            # Erfolgreiche Berechnung?
            success = (hasattr(egea_result, 'is_valid') and egea_result.is_valid and 
                      hasattr(egea_result, 'min_phase_shift') and egea_result.min_phase_shift is not None)
            
            # Minimale Phasenverschiebung
            min_phase_shift = egea_result.min_phase_shift if success else 0.0
            
            # Phase-Shifts aller Perioden für GUI-Charts
            phase_shifts = []
            cycle_count = 0
            
            if hasattr(egea_result, 'periods') and egea_result.periods:
                phase_shifts = [p.phase_shift for p in egea_result.periods if hasattr(p, 'is_valid') and p.is_valid]
                cycle_count = len(egea_result.periods)
            
            # EGEA-Bewertung
            passing = success and min_phase_shift >= self.phase_threshold
            quality_index = min(100, (min_phase_shift / self.phase_threshold) * 100) if success else 0.0
            
            # GUI-kompatibles Ergebnis
            return {
                'success': success,
                'min_phase_shift': float(min_phase_shift) if min_phase_shift is not None else 0.0,
                'phase_shifts': phase_shifts,
                'cycle_count': cycle_count,
                'passing': passing,
                'quality_index': float(quality_index),
                'evaluation': 'passing' if passing else 'failing',
                
                # Erweiterte EGEA-Daten für GUI
                'min_phase_frequency': (getattr(egea_result, 'min_phase_frequency', 0.0) 
                                       if success else 0.0),
                'rfa_max': (getattr(egea_result, 'rfa_max_value', 0.0) 
                           if hasattr(egea_result, 'rfa_max_value') and egea_result.rfa_max_value else 0.0),
                'static_weight': getattr(egea_result, 'static_weight', 0.0),
                'f_under_flag': getattr(egea_result, 'f_under_flag', False),
                'f_over_flag': getattr(egea_result, 'f_over_flag', False),
                
                # Metadaten
                'central_implementation_used': True,
                'egea_compliant': True,
                'periods_analyzed': len(egea_result.periods) if hasattr(egea_result, 'periods') and egea_result.periods else 0
            }
            
        except Exception as e:
            logger.error(f"EGEA-zu-GUI Format-Konvertierung fehlgeschlagen: {e}")
            return self._create_error_result(f"Format conversion failed: {e}")
    
    def _validate_inputs(self, platform_data: np.ndarray, force_data: np.ndarray, 
                        time_data: np.ndarray) -> bool:
        """Validate input data (GUI-level validation)."""
        try:
            if len(platform_data) != len(force_data) or len(platform_data) != len(time_data):
                logger.error("Ungleiche Array-Längen")
                return False
            
            if len(platform_data) < 10:  # Minimum data points für GUI
                logger.error("Zu wenige Datenpunkte für GUI-Processing")
                return False
            
            if np.any(np.isnan(platform_data)) or np.any(np.isnan(force_data)):
                logger.error("NaN-Werte in GUI-Eingabedaten")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"GUI-Input-Validierung fehlgeschlagen: {e}")
            return False
    
    def _generate_cache_key(self, platform_data: np.ndarray, force_data: np.ndarray, 
                          static_weight: float) -> str:
        """Generate cache key for GUI performance."""
        try:
            # Use hash of data for caching (simplified for GUI)
            platform_hash = hash(platform_data.tobytes())
            force_hash = hash(force_data.tobytes())
            return f"gui_{platform_hash}_{force_hash}_{static_weight}"
        except Exception:
            # Fallback cache key
            return f"gui_{len(platform_data)}_{static_weight}_{time.time()}"
    
    def _create_error_result(self, error_message: str) -> Dict[str, Any]:
        """Create GUI-compatible error result."""
        return {
            'success': False,
            'error': error_message,
            'min_phase_shift': 0.0,
            'phase_shifts': [],
            'cycle_count': 0,
            'passing': False,
            'quality_index': 0.0,
            'evaluation': 'error',
            'central_implementation_used': True,
            'egea_compliant': False
        }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for GUI monitoring."""
        if not self.processing_times:
            return {
                'central_implementation': True,
                'cache_available': True
            }
        
        times = list(self.processing_times)
        return {
            'avg_processing_time': np.mean(times),
            'min_processing_time': np.min(times),
            'max_processing_time': np.max(times),
            'total_calculations': len(times),
            'cache_hit_rate': self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0,
            'cache_size': len(self._result_cache),
            
            # EGEA-spezifische Stats
            'central_implementation': True,
            'egea_compliant': True,
            'algorithm_version': 'suspension_core.egea.EGEAPhaseShiftProcessor'
        }
    
    def clear_cache(self):
        """Clear GUI-specific caches."""
        self._result_cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Zentrale Implementation hat eigenes Cache-Management
        # Hier nur GUI-spezifische Caches löschen
        
        logger.info("✅ GUI Phase shift processor cache cleared")


class BackgroundProcessor:
    """
    Background processor for EGEA calculations and data processing.
    
    ✅ MIGRATION: Updated to use central EGEA implementation via PhaseShiftProcessor wrapper
    
    Features:
    - Multi-threaded processing
    - Priority queue for tasks
    - Performance monitoring
    - Central EGEA implementation integration
    - Graceful shutdown
    """
    
    def __init__(self, num_workers: int = None):
        """Initialize background processor with central EGEA integration."""
        
        if not CENTRAL_EGEA_AVAILABLE:
            raise ImportError(
                "Zentrale EGEA-Implementation nicht verfügbar. "
                "Bitte installieren Sie suspension_core."
            )
        
        self.num_workers = num_workers or max(1, mp.cpu_count() - 1)
        
        # Task management
        self.task_queue = queue.PriorityQueue()
        self.result_queue = queue.Queue()
        self.workers = []
        self.running = False
        
        # ✅ ZENTRALE IMPLEMENTATION über GUI-Wrapper
        self.phase_shift_processor = PhaseShiftProcessor()
        
        # Performance tracking
        self.tasks_processed = 0
        self.tasks_failed = 0
        self.start_time = None
        
        # Result callbacks
        self.result_callbacks = {}
        
        logger.info(f"✅ BackgroundProcessor initialized with {self.num_workers} workers "
                   f"(central EGEA implementation)")
    
    def start(self):
        """Start background processing with central EGEA integration."""
        if self.running:
            return
        
        self.running = True
        self.start_time = time.time()
        
        # Start worker threads
        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"BGProcessor-EGEA-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
        
        # Start result dispatcher
        result_dispatcher = threading.Thread(
            target=self._result_dispatcher_loop,
            name="EGEA-ResultDispatcher",
            daemon=True
        )
        result_dispatcher.start()
        
        logger.info(f"✅ Background processor started with {self.num_workers} workers "
                   f"(central EGEA implementation)")
    
    def stop(self):
        """Stop background processing."""
        if not self.running:
            return
        
        self.running = False
        
        # Add stop signals for all workers
        for _ in self.workers:
            self.task_queue.put(ProcessingTask("STOP", "stop", {}, time.time(), priority=9999))
        
        # Wait for workers to finish (with timeout)
        for worker in self.workers:
            worker.join(timeout=1.0)
        
        logger.info("✅ Background processor stopped (central EGEA implementation)")
    
    def submit_task(self, task_type: str, data: Dict[str, Any], 
                   callback: Optional[Callable] = None, priority: int = 0) -> str:
        """Submit a processing task to central EGEA implementation."""
        task_id = f"egea_{task_type}_{time.time()}_{id(data)}"
        
        task = ProcessingTask(
            task_id=task_id,
            task_type=task_type,
            data=data,
            timestamp=time.time(),
            priority=priority
        )
        
        # Store callback if provided
        if callback:
            self.result_callbacks[task_id] = callback
        
        self.task_queue.put(task)
        
        logger.debug(f"✅ EGEA task submitted: {task_type} (id: {task_id})")
        return task_id
    
    def submit_phase_shift_calculation(self, platform_data: np.ndarray, force_data: np.ndarray,
                                     time_data: np.ndarray, static_weight: float,
                                     callback: Optional[Callable] = None) -> str:
        """Submit phase shift calculation to central EGEA implementation."""
        data = {
            'platform_data': platform_data,
            'force_data': force_data,
            'time_data': time_data,
            'static_weight': static_weight
        }
        
        return self.submit_task('phase_shift', data, callback, priority=0)
    
    def _worker_loop(self):
        """Main worker loop using central EGEA implementation."""
        worker_name = threading.current_thread().name
        logger.debug(f"✅ EGEA Worker {worker_name} started")
        
        while self.running:
            try:
                # Get task with timeout
                task = self.task_queue.get(timeout=1.0)
                
                # Check for stop signal
                if task.task_type == "stop":
                    break
                
                # Process task with central implementation
                result = self._process_task(task)
                
                # Queue result
                self.result_queue.put(result)
                
                # Mark task as done
                self.task_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ EGEA Worker {worker_name} error: {e}")
        
        logger.debug(f"✅ EGEA Worker {worker_name} stopped")
    
    def _process_task(self, task: ProcessingTask) -> ProcessingResult:
        """Process a single task using central EGEA implementation."""
        start_time = time.perf_counter()
        
        try:
            if task.task_type == "phase_shift":
                # ✅ ZENTRALE EGEA-IMPLEMENTATION VERWENDEN
                result_data = self.phase_shift_processor.calculate_phase_shift(
                    task.data['platform_data'],
                    task.data['force_data'],
                    task.data['time_data'],
                    task.data['static_weight']
                )
                success = result_data.get('success', False)
                
            else:
                result_data = {
                    'error': f'Unknown task type: {task.task_type}',
                    'central_implementation': True
                }
                success = False
            
            processing_time = time.perf_counter() - start_time
            
            if success:
                self.tasks_processed += 1
                logger.debug(f"✅ EGEA task processed: {task.task_type} in {processing_time:.3f}s")
            else:
                self.tasks_failed += 1
                logger.warning(f"❌ EGEA task failed: {task.task_type}")
            
            return ProcessingResult(
                task_id=task.task_id,
                task_type=task.task_type,
                result=result_data,
                processing_time=processing_time,
                timestamp=time.time(),
                success=success
            )
            
        except Exception as e:
            self.tasks_failed += 1
            processing_time = time.perf_counter() - start_time
            
            logger.error(f"❌ EGEA task processing failed: {e}")
            
            return ProcessingResult(
                task_id=task.task_id,
                task_type=task.task_type,
                result={'error': str(e), 'central_implementation': True},
                processing_time=processing_time,
                timestamp=time.time(),
                success=False,
                error=str(e)
            )
    
    def _result_dispatcher_loop(self):
        """Dispatch results to callbacks."""
        logger.debug("✅ EGEA Result dispatcher started")
        
        while self.running:
            try:
                # Get result with timeout
                result = self.result_queue.get(timeout=1.0)
                
                # Call callback if available
                callback = self.result_callbacks.pop(result.task_id, None)
                if callback:
                    try:
                        callback(result)
                    except Exception as e:
                        logger.error(f"❌ EGEA Callback error for task {result.task_id}: {e}")
                
                # Mark result as processed
                self.result_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ EGEA Result dispatcher error: {e}")
        
        logger.debug("✅ EGEA Result dispatcher stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get processor status with central EGEA information."""
        uptime = time.time() - self.start_time if self.start_time else 0
        
        # Basis-Status
        status = {
            'running': self.running,
            'num_workers': self.num_workers,
            'active_workers': sum(1 for w in self.workers if w.is_alive()),
            'task_queue_size': self.task_queue.qsize(),
            'result_queue_size': self.result_queue.qsize(),
            'tasks_processed': self.tasks_processed,
            'tasks_failed': self.tasks_failed,
            'uptime': uptime,
            'tasks_per_second': self.tasks_processed / uptime if uptime > 0 else 0,
            
            # EGEA-spezifische Information
            'central_implementation': True,
            'egea_available': CENTRAL_EGEA_AVAILABLE,
            'algorithm_version': 'suspension_core.egea.EGEAPhaseShiftProcessor'
        }
        
        # Phase-Shift-Processor-Stats hinzufügen
        try:
            phase_shift_stats = self.phase_shift_processor.get_performance_stats()
            status['phase_shift_stats'] = phase_shift_stats
        except Exception as e:
            logger.warning(f"Konnte Phase-Shift-Stats nicht abrufen: {e}")
            status['phase_shift_stats'] = {'error': str(e)}
        
        return status
    
    def clear_caches(self):
        """Clear all processor caches."""
        try:
            self.phase_shift_processor.clear_cache()
            logger.info("✅ Background processor caches cleared (central EGEA implementation)")
        except Exception as e:
            logger.warning(f"Cache-Clearing fehlgeschlagen: {e}")


# ✅ MIGRATION-INFO bei Import
if __name__ != "__main__":
    if CENTRAL_EGEA_AVAILABLE:
        logger.info("✅ GUI Background Processor geladen (nutzt zentrale EGEA-Implementation)")
    else:
        logger.error("❌ GUI Background Processor: Zentrale EGEA-Implementation nicht verfügbar")
