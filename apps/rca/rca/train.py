"""Train ML model on labeled suspects."""
import os
import sys
import asyncio
import asyncpg
import pickle
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def load_training_data(postgres_pool: asyncpg.Pool) -> tuple:
    """
    Load labeled suspects from database.
    
    Returns:
        (X, y) where X is feature matrix and y is labels
    """
    async with postgres_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT s.evidence, l.label
            FROM suspects s
            JOIN labels l ON s.id = l.suspect_id
            WHERE s.evidence IS NOT NULL
            """
        )
    
    if len(rows) < 10:
        logger.warning(f"Only {len(rows)} labeled examples found. Need at least 10 for training.")
        return None, None
    
    X = []
    y = []
    
    # Feature names (must match ml_ranker.py)
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
    
    for row in rows:
        evidence = row['evidence']
        if isinstance(evidence, str):
            evidence = json.loads(evidence)
        
        # Extract features in order
        features = []
        for name in feature_names:
            features.append(evidence.get(name, 0.0))
        
        X.append(features)
        y.append(row['label'])
    
    return np.array(X), np.array(y)


async def train_model():
    """Train logistic regression model on labeled data."""
    # Connect to Postgres
    postgres_pool = await asyncpg.create_pool(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "rca"),
        user=os.getenv("POSTGRES_USER", "rca"),
        password=os.getenv("POSTGRES_PASSWORD", "rca_password")
    )
    
    try:
        # Load data
        logger.info("Loading training data...")
        X, y = await load_training_data(postgres_pool)
        
        if X is None:
            logger.error("Insufficient training data")
            return
        
        logger.info(f"Loaded {len(X)} labeled examples")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        logger.info(f"Training set: {len(X_train)}, Test set: {len(X_test)}")
        
        # Train model
        logger.info("Training logistic regression model...")
        model = LogisticRegression(
            max_iter=1000,
            random_state=42,
            class_weight='balanced'  # Handle class imbalance
        )
        model.fit(X_train, y_train)
        
        # Evaluate
        y_pred = model.predict(X_test)
        y_pred_proba = model.predict_proba(X_test)[:, 1]
        
        precision = precision_score(y_test, y_pred)
        recall = recall_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred)
        auc = roc_auc_score(y_test, y_pred_proba)
        
        logger.info(f"Test Metrics:")
        logger.info(f"  Precision: {precision:.3f}")
        logger.info(f"  Recall: {recall:.3f}")
        logger.info(f"  F1 Score: {f1:.3f}")
        logger.info(f"  AUC-ROC: {auc:.3f}")
        
        # Save model
        os.makedirs('models', exist_ok=True)
        model_path = 'models/ranker.pkl'
        
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
        
        model_data = {
            'model': model,
            'feature_names': feature_names
        }
        
        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)
        
        logger.info(f"Model saved to {model_path}")
        
    finally:
        await postgres_pool.close()


if __name__ == "__main__":
    asyncio.run(train_model())


