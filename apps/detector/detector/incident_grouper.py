"""Group anomalies into incidents based on time overlap."""
from typing import List, Dict, Tuple
from datetime import datetime, timedelta, timezone
import uuid
import logging

logger = logging.getLogger(__name__)


class IncidentGrouper:
    """Groups anomalies into incidents."""
    
    def __init__(self, gap_minutes: int = 10):
        """
        Args:
            gap_minutes: Maximum gap between anomalies to group them
        """
        self.gap_minutes = gap_minutes
    
    def group_anomalies(
        self,
        anomalies: List[Dict]
    ) -> List[Dict]:
        """
        Group anomalies into incidents.
        
        Args:
            anomalies: List of anomaly dicts with keys:
                - id, start_ts, end_ts, service, metric, score
        
        Returns:
            List of incident dicts with keys:
                - id, start_ts, end_ts, title, status, anomaly_ids
        """
        if not anomalies:
            return []
        
        # Sort anomalies by start time
        sorted_anomalies = sorted(anomalies, key=lambda a: a['start_ts'])
        
        incidents = []
        current_incident = None
        
        for anomaly in sorted_anomalies:
            if current_incident is None:
                # Start new incident
                current_incident = {
                    'id': str(uuid.uuid4()),
                    'start_ts': anomaly['start_ts'],
                    'end_ts': anomaly['end_ts'],
                    'title': f"Incident in {anomaly['service']}",
                    'status': 'OPEN',
                    'anomaly_ids': [anomaly['id']],
                    'services': {anomaly['service']},
                    'metrics': {anomaly['metric']}
                }
            else:
                # Check if anomaly overlaps or is within gap
                gap = (anomaly['start_ts'] - current_incident['end_ts']).total_seconds() / 60
                
                if gap <= self.gap_minutes or anomaly['service'] in current_incident['services']:
                    # Add to current incident
                    current_incident['end_ts'] = max(current_incident['end_ts'], anomaly['end_ts'])
                    current_incident['anomaly_ids'].append(anomaly['id'])
                    current_incident['services'].add(anomaly['service'])
                    current_incident['metrics'].add(anomaly['metric'])
                    
                    # Update title if multiple services
                    if len(current_incident['services']) > 1:
                        services_str = ', '.join(sorted(current_incident['services']))
                        current_incident['title'] = f"Incident affecting {services_str}"
                else:
                    # Close current incident and start new one
                    incidents.append({
                        'id': current_incident['id'],
                        'start_ts': current_incident['start_ts'],
                        'end_ts': current_incident['end_ts'],
                        'title': current_incident['title'],
                        'status': current_incident['status'],
                        'anomaly_ids': current_incident['anomaly_ids']
                    })
                    
                    current_incident = {
                        'id': str(uuid.uuid4()),
                        'start_ts': anomaly['start_ts'],
                        'end_ts': anomaly['end_ts'],
                        'title': f"Incident in {anomaly['service']}",
                        'status': 'OPEN',
                        'anomaly_ids': [anomaly['id']],
                        'services': {anomaly['service']},
                        'metrics': {anomaly['metric']}
                    }
        
        # Add final incident
        if current_incident:
            incidents.append({
                'id': current_incident['id'],
                'start_ts': current_incident['start_ts'],
                'end_ts': current_incident['end_ts'],
                'title': current_incident['title'],
                'status': current_incident['status'],
                'anomaly_ids': current_incident['anomaly_ids']
            })
        
        return incidents


