"""Robust z-score anomaly detection using median and MAD."""
import numpy as np
from typing import List, Tuple, Optional
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Detects anomalies using robust z-score (median + MAD)."""
    
    def __init__(
        self,
        z_threshold: float = 3.0,
        min_points: int = 5,
        lookback_days: int = 7,
        bad_directions: dict = None
    ):
        """
        Args:
            z_threshold: Z-score threshold for anomaly detection
            min_points: Minimum points needed for baseline calculation
            lookback_days: Days to look back for baseline
            bad_directions: Dict mapping metric names to 'up' or 'down' for bad direction
        """
        self.z_threshold = z_threshold
        self.min_points = min_points
        self.lookback_days = lookback_days
        self.bad_directions = bad_directions or {
            'p95_latency_ms': 'up',
            'p99_latency_ms': 'up',
            'error_rate': 'up',
            'qps': 'down'  # QPS going down is bad
        }
    
    def compute_baseline(self, values: List[float]) -> Tuple[float, float]:
        """
        Compute baseline using median and MAD.
        
        Returns:
            (median, mad) tuple
        """
        if len(values) < self.min_points:
            return None, None
        
        values_array = np.array(values)
        median = np.median(values_array)
        
        # MAD = median absolute deviation
        deviations = np.abs(values_array - median)
        mad = np.median(deviations)
        
        # Scale MAD to approximate standard deviation (for normal distribution)
        # 1.4826 is the scaling factor
        scaled_mad = 1.4826 * mad
        
        return median, scaled_mad
    
    def is_anomaly(
        self,
        value: float,
        baseline_median: float,
        baseline_mad: float,
        metric: str
    ) -> bool:
        """
        Check if a value is an anomaly.
        
        Args:
            value: Current value
            baseline_median: Baseline median
            baseline_mad: Baseline MAD (scaled)
            metric: Metric name to check bad direction
        
        Returns:
            True if anomaly
        """
        if baseline_median is None or baseline_mad is None:
            return False
        
        # Avoid division by zero
        if baseline_mad < 1e-6:
            baseline_mad = 1e-6
        
        # Compute robust z-score
        z_score = abs(value - baseline_median) / baseline_mad
        
        # Check if exceeds threshold
        if z_score <= self.z_threshold:
            return False
        
        # Check bad direction
        bad_direction = self.bad_directions.get(metric, 'up')
        if bad_direction == 'up' and value < baseline_median:
            return False  # Going down is not bad for this metric
        elif bad_direction == 'down' and value > baseline_median:
            return False  # Going up is not bad for this metric
        
        return True
    
    def detect_anomalies_in_window(
        self,
        values: List[float],
        timestamps: List[datetime],
        metric: str,
        window_minutes: int = 5,
        required_anomalies: int = 3
    ) -> List[Tuple[datetime, datetime, float]]:
        """
        Detect anomalies in a time window.
        
        Args:
            values: List of metric values
            timestamps: List of timestamps
            metric: Metric name
            window_minutes: Window size in minutes
            required_anomalies: Number of anomalies required in window
        
        Returns:
            List of (start_ts, end_ts, max_score) tuples
        """
        if len(values) < self.min_points + required_anomalies:
            return []
        
        # Use first N points for baseline (excluding recent window)
        baseline_size = min(len(values) - window_minutes, self.lookback_days * 24 * 60)
        baseline_values = values[:baseline_size]
        
        baseline_median, baseline_mad = self.compute_baseline(baseline_values)
        if baseline_median is None:
            return []
        
        anomalies = []
        window_start_idx = len(values) - window_minutes
        
        # Check last window_minutes points
        anomaly_count = 0
        max_z_score = 0.0
        window_start = None
        window_end = None
        
        for i in range(window_start_idx, len(values)):
            value = values[i]
            ts = timestamps[i]
            
            if baseline_mad < 1e-6:
                z_score = 0.0
            else:
                z_score = abs(value - baseline_median) / baseline_mad
            
            is_anom = self.is_anomaly(value, baseline_median, baseline_mad, metric)
            
            if is_anom:
                if window_start is None:
                    window_start = ts
                window_end = ts
                anomaly_count += 1
                max_z_score = max(max_z_score, z_score)
            else:
                # If we had a window, check if it qualifies
                if anomaly_count >= required_anomalies and window_start:
                    anomalies.append((window_start, window_end, max_z_score))
                anomaly_count = 0
                max_z_score = 0.0
                window_start = None
                window_end = None
        
        # Check final window
        if anomaly_count >= required_anomalies and window_start:
            anomalies.append((window_start, window_end, max_z_score))
        
        return anomalies


