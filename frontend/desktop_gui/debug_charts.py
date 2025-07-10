"""
Debug-Utilities für Chart-Probleme
"""

import logging
import numpy as np
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


def analyze_data_quality(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analysiert die Datenqualität und gibt Statistiken zurück.
    
    Args:
        data: Dictionary mit Messdaten
        
    Returns:
        Dictionary mit Statistiken pro Datenfeld
    """
    stats = {}
    
    for key, values in data.items():
        if isinstance(values, (list, np.ndarray)) and len(values) > 0:
            try:
                arr = np.array(values, dtype=float)
                
                # Basis-Statistiken
                valid_mask = np.isfinite(arr)
                valid_values = arr[valid_mask]
                invalid_count = len(arr) - len(valid_values)
                
                stats[key] = {
                    'total_count': len(arr),
                    'valid_count': len(valid_values),
                    'invalid_count': invalid_count,
                    'invalid_percentage': (invalid_count / len(arr)) * 100 if len(arr) > 0 else 0,
                    'nan_count': np.sum(np.isnan(arr)),
                    'inf_count': np.sum(np.isinf(arr)),
                }
                
                if len(valid_values) > 0:
                    stats[key].update({
                        'min': float(np.min(valid_values)),
                        'max': float(np.max(valid_values)),
                        'mean': float(np.mean(valid_values)),
                        'std': float(np.std(valid_values)),
                        'median': float(np.median(valid_values)),
                    })
                    
                    # Ausreißer-Erkennung
                    if len(valid_values) > 3:
                        q1 = np.percentile(valid_values, 25)
                        q3 = np.percentile(valid_values, 75)
                        iqr = q3 - q1
                        lower_bound = q1 - 1.5 * iqr
                        upper_bound = q3 + 1.5 * iqr
                        outliers = valid_values[(valid_values < lower_bound) | (valid_values > upper_bound)]
                        
                        stats[key]['outlier_count'] = len(outliers)
                        stats[key]['outlier_percentage'] = (len(outliers) / len(valid_values)) * 100
                        stats[key]['iqr_bounds'] = (float(lower_bound), float(upper_bound))
                
            except Exception as e:
                stats[key] = {'error': str(e)}
    
    return stats


def log_data_issues(data: Dict[str, Any], context: str = ""):
    """
    Loggt Datenqualitätsprobleme für Debugging.
    
    Args:
        data: Dictionary mit Messdaten
        context: Zusätzlicher Kontext für die Log-Nachricht
    """
    try:
        stats = analyze_data_quality(data)
        
        issues_found = False
        for field, field_stats in stats.items():
            if isinstance(field_stats, dict) and 'error' not in field_stats:
                if field_stats.get('invalid_percentage', 0) > 10:
                    logger.warning(f"{context} - Field '{field}': {field_stats['invalid_percentage']:.1f}% invalid values "
                                 f"(NaN: {field_stats.get('nan_count', 0)}, Inf: {field_stats.get('inf_count', 0)})")
                    issues_found = True
                
                if field_stats.get('outlier_percentage', 0) > 20:
                    logger.warning(f"{context} - Field '{field}': {field_stats['outlier_percentage']:.1f}% outliers detected")
                    issues_found = True
        
        if issues_found:
            logger.debug(f"{context} - Full statistics: {stats}")
            
    except Exception as e:
        logger.error(f"Error in log_data_issues: {e}")


def create_test_data(include_errors: bool = False) -> Dict[str, List[float]]:
    """
    Erstellt Testdaten für Chart-Debugging.
    
    Args:
        include_errors: Ob fehlerhafte Werte eingefügt werden sollen
        
    Returns:
        Dictionary mit Testdaten
    """
    t = np.linspace(0, 10, 100)
    
    # Saubere Sinuswellen
    platform = 50 * np.sin(2 * np.pi * 1.5 * t)
    force = 2000 + 500 * np.sin(2 * np.pi * 1.5 * t + np.pi/4)
    phase = 45 + 20 * np.sin(2 * np.pi * 0.5 * t)
    frequency = 12 + 2 * np.sin(2 * np.pi * 0.2 * t)
    
    if include_errors:
        # Füge fehlerhafte Werte hinzu
        platform[10:12] = np.nan
        force[30] = np.inf
        phase[50:55] = 1000  # Extremer Ausreißer
        frequency[70] = -10  # Negativer Wert
    
    return {
        'time': t.tolist(),
        'platform_position': platform.tolist(),
        'tire_force': force.tolist(),
        'phase_shift': phase.tolist(),
        'frequency': frequency.tolist()
    }


class DataQualityMonitor:
    """
    Überwacht kontinuierlich die Datenqualität.
    """
    
    def __init__(self, warning_threshold: float = 0.1):
        """
        Args:
            warning_threshold: Schwellwert für Warnungen (0.1 = 10% fehlerhafte Werte)
        """
        self.warning_threshold = warning_threshold
        self.history = []
        self.issue_count = 0
        
    def check_data(self, data: Dict[str, Any]) -> bool:
        """
        Prüft Daten und gibt True zurück wenn Probleme gefunden wurden.
        """
        stats = analyze_data_quality(data)
        
        has_issues = False
        for field, field_stats in stats.items():
            if isinstance(field_stats, dict) and 'error' not in field_stats:
                invalid_ratio = field_stats.get('invalid_percentage', 0) / 100
                if invalid_ratio > self.warning_threshold:
                    has_issues = True
                    self.issue_count += 1
                    
                    if self.issue_count % 10 == 1:  # Log nur jeden 10. Fehler
                        logger.warning(f"Data quality issue in '{field}': "
                                     f"{field_stats['invalid_percentage']:.1f}% invalid values")
        
        self.history.append({
            'timestamp': time.time(),
            'stats': stats,
            'has_issues': has_issues
        })
        
        # Behalte nur die letzten 100 Einträge
        if len(self.history) > 100:
            self.history.pop(0)
        
        return has_issues
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Gibt eine Zusammenfassung der Datenqualität zurück.
        """
        if not self.history:
            return {'status': 'No data collected'}
        
        recent_issues = sum(1 for entry in self.history[-10:] if entry['has_issues'])
        
        return {
            'total_checks': len(self.history),
            'total_issues': self.issue_count,
            'recent_issue_rate': recent_issues / min(len(self.history), 10),
            'last_check': self.history[-1]['timestamp'] if self.history else None
        }