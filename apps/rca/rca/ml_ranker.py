"""ML-based ranker using trained model."""
from typing import List, Dict, Any
import os
import pickle
import logging
import numpy as np
from sklearn.linear_model import LogisticRegression

logger = logging.getLogger(__name__)


class MLRanker:
    """ML-based ranker that loads a trained model."""
    
    def __init__(self, model_path: str = None):
        """
        Args:
            model_path: Path to saved model pickle file
        """
        self.model_path = model_path or os.getenv('ML_MODEL_PATH', 'models/ranker.pkl')
        self.model: LogisticRegression = None
        self.feature_names = None
        self.load_model()
    
    def load_model(self):
        """Load trained model from disk."""
        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, 'rb') as f:
                    model_data = pickle.load(f)
                    self.model = model_data['model']
                    self.feature_names = model_data['feature_names']
                logger.info(f"Loaded ML model from {self.model_path}")
            else:
                logger.warning(f"Model file not found at {self.model_path}, using heuristic fallback")
                self.model = None
        except Exception as e:
            logger.error(f"Failed to load model: {e}, using heuristic fallback")
            self.model = None
    
    def rank(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rank candidates using ML model if available, otherwise fallback to heuristic.
        
        Args:
            candidates: List of candidate dicts with 'evidence' key
        
        Returns:
            List of candidates sorted by score (descending), with 'rank' and 'score' added
        """
        if self.model is None:
            # Fallback to heuristic
            from rca.ranker import HeuristicRanker
            heuristic_ranker = HeuristicRanker()
            return heuristic_ranker.rank(candidates)
        
        # Extract features
        X = []
        for candidate in candidates:
            features = self._extract_features(candidate.get('evidence', {}))
            X.append(features)
        
        X = np.array(X)
        
        # Predict probabilities
        probabilities = self.model.predict_proba(X)
        # Use probability of positive class (index 1)
        scores = probabilities[:, 1] if probabilities.shape[1] > 1 else probabilities[:, 0]
        
        # Add scores to candidates
        scored = []
        for i, candidate in enumerate(candidates):
            scored.append({
                **candidate,
                'score': float(scores[i])
            })
        
        # Sort by score descending
        scored.sort(key=lambda x: x['score'], reverse=True)
        
        # Add rank
        for i, candidate in enumerate(scored):
            candidate['rank'] = i + 1
        
        return scored
    
    def _extract_features(self, evidence: Dict[str, float]) -> List[float]:
        """Extract features in the same order as training."""
        if self.feature_names is None:
            # Default feature order (should match training)
            feature_names = [
                'is_before_incident',
                'time_proximity_score',
                'minutes_before_incident',
                'metric_delta_count',
                'max_metric_delta',
                'avg_metric_delta',
                'error_log_delta',
                'new_error_signature',
                'diff_keyword_hit',
                'diff_keyword_count',
                'service_incident_rate_30d'
            ]
        else:
            feature_names = self.feature_names
        
        features = []
        for name in feature_names:
            features.append(evidence.get(name, 0.0))
        
        return features


