# models/random_forest.py — Model 2: Failure Prediction for InfraGuard AI

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from database import get_metric_history
from config import Config


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURES — same 8 metrics as Isolation Forest
# ══════════════════════════════════════════════════════════════════════════════

FEATURES = ['cpu', 'ram', 'disk', 'network_in', 'network_out',
            'temperature', 'response_time', 'error_rate']

def extract_features(metric_row):
    return [float(metric_row.get(f, 0) or 0) for f in FEATURES]


# ══════════════════════════════════════════════════════════════════════════════
#  LABEL GENERATOR — creates training labels from raw metrics
#  Since we have no real failure history, we generate labels using
#  threshold rules — this is standard practice for synthetic datasets
# ══════════════════════════════════════════════════════════════════════════════

def generate_label(metric_row):
    """
    Returns 1 (failure risk) or 0 (healthy) based on threshold rules.
    This teaches the model what failure conditions look like.
    """
    cpu   = metric_row.get('cpu', 0) or 0
    ram   = metric_row.get('ram', 0) or 0
    disk  = metric_row.get('disk', 0) or 0
    temp  = metric_row.get('temperature', 0) or 0
    err   = metric_row.get('error_rate', 0) or 0
    rt    = metric_row.get('response_time', 0) or 0

    # Any of these conditions = failure risk
    if (cpu > 90 or ram > 90 or disk > 90 or
            temp > 80 or err > 8 or rt > 1800):
        return 1   # failure risk
    return 0       # healthy


# ══════════════════════════════════════════════════════════════════════════════
#  RANDOM FOREST MODEL CLASS
# ══════════════════════════════════════════════════════════════════════════════

class RandomForestModel:

    def __init__(self, server_id):
        self.server_id  = server_id
        self.model      = None
        self.scaler     = StandardScaler()
        self.is_trained = False
        self.min_samples = 30


    def _load_training_data(self):
        """Load history and generate labels."""
        history = get_metric_history(self.server_id, limit=500)
        if len(history) < self.min_samples:
            return None, None

        X = [extract_features(row) for row in history]
        y = [generate_label(row)   for row in history]

        # If all labels are the same, add a few synthetic failure examples
        # so the model learns both classes
        if sum(y) == 0:
            # Add 5 synthetic failure rows
            failure_row = {
                'cpu': 95, 'ram': 93, 'disk': 92,
                'network_in': 900, 'network_out': 900,
                'temperature': 85, 'response_time': 2000, 'error_rate': 12
            }
            for _ in range(5):
                X.append(extract_features(failure_row))
                y.append(1)

        return np.array(X), np.array(y)


    def train(self):
        """Train the Random Forest classifier."""
        X, y = self._load_training_data()
        if X is None:
            return False

        X_scaled = self.scaler.fit_transform(X)

        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            class_weight='balanced'   # handles imbalanced failure vs healthy
        )
        self.model.fit(X_scaled, y)
        self.is_trained = True
        return True


    def predict(self, metric_data):
        """
        Predict failure probability for one reading.
        Returns dict with probability, risk level, and feature importance.
        """
        if not self.is_trained:
            trained = self.train()
            if not trained:
                return {
                    'failure_probability': 0.0,
                    'risk_level':          'UNKNOWN',
                    'feature_importance':  {},
                    'trained':             False
                }

        features = extract_features(metric_data)
        X        = np.array([features])
        X_scaled = self.scaler.transform(X)

# Get probability of failure (class 1)
        proba = self.model.predict_proba(X_scaled)[0]
        # If model only learned one class, proba has 1 value — handle safely
        if len(proba) == 1:
            failure_prob = 0.0
        else:
            failure_prob = round(float(proba[1]) * 100, 2)

        # Risk level
        if failure_prob >= 75:
            risk_level = 'CRITICAL'
        elif failure_prob >= 50:
            risk_level = 'HIGH'
        elif failure_prob >= 25:
            risk_level = 'MEDIUM'
        else:
            risk_level = 'LOW'

        # Feature importance — which metric matters most right now
        importances = self.model.feature_importances_
        feature_importance = {
            FEATURES[i]: round(float(importances[i]) * 100, 2)
            for i in range(len(FEATURES))
        }
        # Sort by importance descending
        feature_importance = dict(
            sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
        )

        # Top reason — the most important feature
        top_feature = list(feature_importance.keys())[0]
        top_value   = metric_data.get(top_feature, 0)

        return {
            'failure_probability': failure_prob,
            'risk_level':          risk_level,
            'feature_importance':  feature_importance,
            'top_reason':          top_feature,
            'top_value':           top_value,
            'trained':             True
        }


    def retrain_if_needed(self):
        from database import get_metric_count
        count = get_metric_count(self.server_id)
        if count > 0 and count % Config.AI_RETRAIN_EVERY == 0:
            self.train()
            return True
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  MANAGER — One model per server
# ══════════════════════════════════════════════════════════════════════════════

class RandomForestManager:

    def __init__(self):
        self.models = {}
        for server in Config.SERVERS:
            self.models[server['id']] = RandomForestModel(server['id'])


    def predict(self, server_id, metric_data):
        if server_id not in self.models:
            return None
        return self.models[server_id].predict(metric_data)


    def predict_all(self, latest_data):
        results = {}
        for server_id, data in latest_data.items():
            results[server_id] = self.predict(server_id, data)
        return results


    def train_all(self):
        trained_count = 0
        for server_id, model in self.models.items():
            if model.train():
                trained_count += 1
        return trained_count


# ══════════════════════════════════════════════════════════════════════════════
#  RUN DIRECTLY — Test the model
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    from database import init_db
    from collector import CollectionEngine

    print("=== InfraGuard AI — Random Forest Test ===\n")
    init_db()

    # ── Step 1: Generate training data ───────────────────────────────────────
    print("Step 1: Generating training data...")
    engine = CollectionEngine()
    for i in range(50):
        engine.collect_all()
    print("  ✅ Training data ready\n")

    # ── Step 2: Train models ──────────────────────────────────────────────────
    print("Step 2: Training Random Forest for all 9 servers...")
    manager = RandomForestManager()
    trained = manager.train_all()
    print(f"  ✅ Trained {trained}/9 models\n")

    # ── Step 3: Predict on healthy server ────────────────────────────────────
    print("Step 3: Healthy server (expect LOW risk)")
    healthy = {
        'cpu': 35.0, 'ram': 55.0, 'disk': 45.0,
        'network_in': 20.0, 'network_out': 15.0,
        'temperature': 52.0, 'response_time': 150.0, 'error_rate': 0.3
    }
    result = manager.predict('web_server_1', healthy)
    print(f"  Failure Probability : {result['failure_probability']}%")
    print(f"  Risk Level          : {result['risk_level']}")
    print(f"  Top Reason          : {result['top_reason']} = {result['top_value']}")
    print(f"  Feature Importance  :")
    for feat, imp in result['feature_importance'].items():
        bar = '█' * int(imp / 5)
        print(f"    {feat:15} {imp:5.1f}%  {bar}")

    # ── Step 4: Predict on failing server ────────────────────────────────────
    print("\nStep 4: Failing server (expect HIGH or CRITICAL risk)")
    failing = {
        'cpu': 95.0, 'ram': 92.0, 'disk': 91.0,
        'network_in': 800.0, 'network_out': 750.0,
        'temperature': 83.0, 'response_time': 2500.0, 'error_rate': 11.0
    }
    result = manager.predict('web_server_1', failing)
    print(f"  Failure Probability : {result['failure_probability']}%")
    print(f"  Risk Level          : {result['risk_level']}")
    print(f"  Top Reason          : {result['top_reason']} = {result['top_value']}")

    # ── Step 5: All servers ───────────────────────────────────────────────────
    print("\nStep 5: All 9 servers with latest data")
    engine.collect_all()
    latest  = engine.get_latest()
    results = manager.predict_all(latest)

    for server in Config.SERVERS:
        sid = server['id']
        r   = results.get(sid, {})
        if r:
            prob  = r.get('failure_probability', 0)
            risk  = r.get('risk_level', 'UNKNOWN')
            icon  = {'CRITICAL':'🔴','HIGH':'🟠','MEDIUM':'🟡','LOW':'🟢'}.get(risk,'⚪')
            print(f"  {icon} {server['name']:20} {prob:5.1f}% failure  →  {risk}")

    print("\n✅ Random Forest test complete!")