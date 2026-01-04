"""Rank suspects using heuristic scoring (upgradeable to ML)."""
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class HeuristicRanker:
    """Heuristic-based ranker (v1)."""
    
    def rank(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rank candidates by heuristic score.
        
        Args:
            candidates: List of candidate dicts with 'evidence' key containing features
        
        Returns:
            List of candidates sorted by score (descending), with 'rank' and 'score' added
        """
        scored = []
        
        for candidate in candidates:
            evidence = candidate.get('evidence', {})
            score = self._compute_score(evidence)
            
            scored.append({
                **candidate,
                'score': score
            })
        
        # Sort by score descending
        scored.sort(key=lambda x: x['score'], reverse=True)
        
        # Add rank
        for i, candidate in enumerate(scored):
            candidate['rank'] = i + 1
        
        return scored
    
    def _compute_score(self, evidence: Dict[str, float]) -> float:
        """
        Compute heuristic score from evidence features.
        
        Formula:
        score = 
            + 3.0 * is_before_incident
            + 2.0 * exp(-minutes_from_start / 30)
            + 2.5 * normalized_metric_delta
            + 2.0 * normalized_log_spike
            + 1.0 * diff_keyword_hit
        """
        import math
        
        score = 0.0
        
        # Time proximity
        is_before = evidence.get('is_before_incident', 0.0)
        score += 3.0 * is_before
        
        if is_before > 0:
            minutes_before = evidence.get('minutes_before_incident', 60.0)
            time_decay = math.exp(-abs(minutes_before) / 30.0)
            score += 2.0 * time_decay
        
        # Metric deltas (normalized)
        max_delta = evidence.get('max_metric_delta', 0.0)
        normalized_delta = min(1.0, max_delta)  # Cap at 1.0
        score += 2.5 * normalized_delta
        
        # Log spike (normalized)
        error_delta = evidence.get('error_log_delta', 0.0)
        normalized_log = min(1.0, max(0.0, error_delta / 10.0))  # Normalize assuming 10x is max
        score += 2.0 * normalized_log
        
        # New error signature
        new_error = evidence.get('new_error_signature', 0.0)
        score += 1.5 * new_error
        
        # Diff keywords
        keyword_hit = evidence.get('diff_keyword_hit', 0.0)
        score += 1.0 * keyword_hit
        
        return score


