# models/isolation_forest.py — Model 1: Anomaly Detection for InfraGuard AI

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from database import get_metric_history, save_prediction
from config import Config


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURE EXTRACTION — Convert raw metric dict into a number array
# ══════════════════════════════════════════════════════════════════════════════

FEATURES = ['cpu', 'ram', 'disk', 'network_in', 'network_out',
            'temperature', 'response_time', 'error_rate']

def extract_features(metric_row):
    """Pull the 8 numeric features out of one metric row."""
    return [float(metric_row.get(f, 0) or 0) for f in FEATURES]


# ══════════════════════════════════════════════════════════════════════════════
#  ISOLATION FOREST MODEL CLASS
# ══════════════════════════════════════════════════════════════════════════════

class IsolationForestModel:
    """
    Wraps sklearn's IsolationForest with:
    - Auto-training from database history
    - StandardScaler normalization
    - Human-readable anomaly scores
    - Per-server model instances
    """

    def __init__(self, server_id):
        self.server_id   = server_id
        self.model       = None
        self.scaler      = StandardScaler()
        self.is_trained  = False
        self.min_samples = 30   # need at least 30 readings before training


    def _load_training_data(self):
        """Load metric history from DB and convert to feature matrix."""
        history = get_metric_history(self.server_id, limit=500)
        if len(history) < self.min_samples:
            return None

        X = [extract_features(row) for row in history]
        return np.array(X)


    def train(self):
        """Train the Isolation Forest on this server's history."""
        X = self._load_training_data()
        if X is None:
            return False   # not enough data yet

        # Normalize features so no single metric dominates
        X_scaled = self.scaler.fit_transform(X)

        # Train the model
        # contamination=0.05 means we expect ~5% of readings to be anomalies
        self.model = IsolationForest(
            n_estimators=100,
            contamination=0.05,
            random_state=42
        )
        self.model.fit(X_scaled)
        self.is_trained = True
        return True


    def predict(self, metric_data):
        """
        Score one reading.
        Returns a dict with anomaly_score (0.0–1.0) and label.
        """
        # If not trained yet, train now
        if not self.is_trained:
            trained = self.train()
            if not trained:
                # Not enough data — return neutral score
                return {
                    'anomaly_score': 0.0,
                    'label':         'Insufficient Data',
                    'is_anomaly':    False,
                    'trained':       False
                }

        # Extract and scale features
        features = extract_features(metric_data)
        X        = np.array([features])
        X_scaled = self.scaler.transform(X)

        # Get raw score from sklearn
        # sklearn returns: -1 (anomaly) or 1 (normal) from predict()
        # score_samples() gives continuous score — more negative = more anomalous
        raw_score = self.model.score_samples(X_scaled)[0]

        # Convert to 0.0–1.0 scale
        # Raw scores typically range from about -0.7 to +0.1
        # We map this to 0.0 (normal) → 1.0 (anomalous)
        anomaly_score = self._normalize_score(raw_score)

        # Determine label
        if anomaly_score >= 0.8:
            label      = 'Severe Anomaly'
            is_anomaly = True
        elif anomaly_score >= 0.6:
            label      = 'Anomaly'
            is_anomaly = True
        elif anomaly_score >= 0.4:
            label      = 'Suspicious'
            is_anomaly = True
        else:
            label      = 'Normal'
            is_anomaly = False

        return {
            'anomaly_score': round(anomaly_score, 4),
            'label':         label,
            'is_anomaly':    is_anomaly,
            'trained':       True
        }


    def _normalize_score(self, raw_score):
        """Map sklearn's raw score to a clean 0.0–1.0 scale."""
        # Clamp raw score to expected range
        clamped = max(-0.8, min(0.1, raw_score))
        # Flip and normalize: -0.8 → 1.0,  0.1 → 0.0
        normalized = (0.1 - clamped) / (0.1 - (-0.8))
        return round(max(0.0, min(1.0, normalized)), 4)


    def retrain_if_needed(self):
        """Retrain every Config.AI_RETRAIN_EVERY new readings."""
        from database import get_metric_count
        count = get_metric_count(self.server_id)
        if count > 0 and count % Config.AI_RETRAIN_EVERY == 0:
            self.train()
            return True
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  MANAGER — One model per server, managed centrally
# ══════════════════════════════════════════════════════════════════════════════

class IsolationForestManager:
    """Manages one IsolationForestModel instance per server."""

    def __init__(self):
        self.models = {}
        for server in Config.SERVERS:
            self.models[server['id']] = IsolationForestModel(server['id'])


    def predict(self, server_id, metric_data):
        """Score one server's latest reading."""
        if server_id not in self.models:
            return None
        return self.models[server_id].predict(metric_data)


    def predict_all(self, latest_data):
        """
        Score all servers at once.
        latest_data = dict from CollectionEngine.get_latest()
        Returns dict: { server_id: result_dict }
        """
        results = {}
        for server_id, data in latest_data.items():
            results[server_id] = self.predict(server_id, data)
        return results


    def train_all(self):
        """Train models for all servers."""
        trained_count = 0
        for server_id, model in self.models.items():
            if model.train():
                trained_count += 1
        return trained_count


    def get_status(self):
        """Return training status for all models."""
        return {
            sid: {
                'trained':   m.is_trained,
                'server_id': sid
            }
            for sid, m in self.models.items()
        }


# ══════════════════════════════════════════════════════════════════════════════
#  RUN DIRECTLY — Test the model
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import time
    from database import init_db
    from collector import CollectionEngine

    print("=== InfraGuard AI — Isolation Forest Test ===\n")
    init_db()

    # ── Step 1: Generate training data ───────────────────────────────────────
    print("Step 1: Generating training data (50 readings per server)...")
    engine = CollectionEngine()
    for i in range(50):
        engine.collect_all()
    print(f"  ✅ Training data ready\n")

    # ── Step 2: Train models ──────────────────────────────────────────────────
    print("Step 2: Training Isolation Forest for all 9 servers...")
    manager      = IsolationForestManager()
    trained      = manager.train_all()
    print(f"  ✅ Trained {trained}/9 models\n")

    # ── Step 3: Score normal data ─────────────────────────────────────────────
    print("Step 3: Scoring NORMAL metrics (expect low scores)")
    normal = {
        'cpu': 40.0, 'ram': 60.0, 'disk': 50.0,
        'network_in': 30.0, 'network_out': 20.0,
        'temperature': 55.0, 'response_time': 200.0, 'error_rate': 0.5
    }
    result = manager.predict('web_server_1', normal)
    print(f"  Score: {result['anomaly_score']}  Label: {result['label']}")
    print(f"  Is anomaly: {result['is_anomaly']}\n")

    # ── Step 4: Score anomalous data ──────────────────────────────────────────
    print("Step 4: Scoring ANOMALOUS metrics (expect high scores)")
    anomalous = {
        'cpu': 98.0, 'ram': 97.0, 'disk': 95.0,
        'network_in': 999.0, 'network_out': 999.0,
        'temperature': 90.0, 'response_time': 5000.0, 'error_rate': 25.0
    }
    result = manager.predict('web_server_1', anomalous)
    print(f"  Score: {result['anomaly_score']}  Label: {result['label']}")
    print(f"  Is anomaly: {result['is_anomaly']}\n")

    # ── Step 5: Score all servers ─────────────────────────────────────────────
    print("Step 5: Scoring all 9 servers with latest data")
    engine.collect_all()
    latest  = engine.get_latest()
    results = manager.predict_all(latest)

    for server in Config.SERVERS:
        sid = server['id']
        r   = results.get(sid, {})
        if r:
            score = r.get('anomaly_score', 0)
            label = r.get('label', 'Unknown')
            icon  = '🔴' if score >= 0.6 else ('🟡' if score >= 0.4 else '🟢')
            print(f"  {icon} {server['name']:20} Score: {score:.4f}  →  {label}")

    print("\n✅ Isolation Forest test complete!")