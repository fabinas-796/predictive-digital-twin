# models/autoencoder.py — Model 4: Deep Pattern Recognition for InfraGuard AI

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import warnings
warnings.filterwarnings('ignore')

from sklearn.preprocessing import MinMaxScaler
from database import get_metric_history
from config import Config


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURES
# ══════════════════════════════════════════════════════════════════════════════

FEATURES = ['cpu', 'ram', 'disk', 'network_in', 'network_out',
            'temperature', 'response_time', 'error_rate']

def extract_features(metric_row):
    return [float(metric_row.get(f, 0) or 0) for f in FEATURES]


# ══════════════════════════════════════════════════════════════════════════════
#  AUTOENCODER MODEL CLASS
# ══════════════════════════════════════════════════════════════════════════════

class AutoencoderModel:
    """
    Autoencoder neural network that:
    1. Learns to compress 8 metrics → 4 values (encoder)
    2. Learns to reconstruct 4 values → 8 metrics (decoder)
    3. High reconstruction error = anomaly
    """

    def __init__(self, server_id):
        self.server_id        = server_id
        self.model            = None
        self.scaler           = MinMaxScaler()
        self.is_trained       = False
        self.threshold        = None   # error above this = anomaly
        self.min_samples      = 40
        self.n_features       = len(FEATURES)


    def _load_data(self):
        """Load and scale metric history."""
        history = get_metric_history(self.server_id, limit=500)
        if len(history) < self.min_samples:
            return None

        X = [extract_features(row) for row in history]
        return np.array(X)


    def train(self):
        """Build and train the Autoencoder."""
        try:
            from tensorflow.keras.models import Model
            from tensorflow.keras.layers import Input, Dense
            from tensorflow.keras.optimizers import Adam

            X = self._load_data()
            if X is None:
                return False

            # Scale to 0–1
            X_scaled = self.scaler.fit_transform(X)

            # ── Build Autoencoder architecture ────────────────────────────────
            # Input layer
            input_layer = Input(shape=(self.n_features,))

            # Encoder — compress 8 → 4
            encoded = Dense(6, activation='relu')(input_layer)
            encoded = Dense(4, activation='relu')(encoded)

            # Decoder — reconstruct 4 → 8
            decoded = Dense(6, activation='relu')(encoded)
            decoded = Dense(self.n_features, activation='sigmoid')(decoded)

            # Full autoencoder model
            self.model = Model(input_layer, decoded)
            self.model.compile(
                optimizer=Adam(learning_rate=0.001),
                loss='mse'
            )

            # Train — input = output (it learns to reproduce itself)
            self.model.fit(
                X_scaled, X_scaled,
                epochs=50,
                batch_size=16,
                validation_split=0.1,
                verbose=0
            )

            # ── Calculate anomaly threshold ───────────────────────────────────
            # Run training data through model and get reconstruction errors
            reconstructed   = self.model.predict(X_scaled, verbose=0)
            errors          = np.mean(np.power(X_scaled - reconstructed, 2), axis=1)

            # Threshold = mean + 2 standard deviations
            # Anything above this is considered anomalous
            self.threshold  = float(np.mean(errors) + 2 * np.std(errors))

            self.is_trained = True
            return True

        except Exception as e:
            print(f"  [Autoencoder Train Error] {e}")
            return False


    def predict(self, metric_data):
        """
        Calculate reconstruction error for one reading.
        High error = the model couldn't reconstruct it = anomaly.
        """
        if not self.is_trained:
            trained = self.train()
            if not trained:
                return {
                    'reconstruction_error': 0.0,
                    'anomaly_score':        0.0,
                    'label':                'Insufficient Data',
                    'is_anomaly':           False,
                    'trained':              False
                }

        # Scale input
        features = extract_features(metric_data)
        X        = np.array([features])
        X_scaled = self.scaler.transform(X)

        # Reconstruct
        reconstructed = self.model.predict(X_scaled, verbose=0)

        # Reconstruction error (MSE)
        error = float(np.mean(np.power(X_scaled - reconstructed, 2)))

        # Normalize error to 0–1 scale using threshold
        # error at threshold = 0.5, above = closer to 1.0
        if self.threshold and self.threshold > 0:
            anomaly_score = min(1.0, error / (self.threshold * 2))
        else:
            anomaly_score = 0.0

        anomaly_score = round(anomaly_score, 4)
        is_anomaly    = error > self.threshold if self.threshold else False

        # Label
        if anomaly_score >= 0.8:
            label = 'Severe Pattern Anomaly'
        elif anomaly_score >= 0.6:
            label = 'Pattern Anomaly'
        elif anomaly_score >= 0.4:
            label = 'Suspicious Pattern'
        else:
            label = 'Normal Pattern'

        return {
            'reconstruction_error': round(error, 6),
            'anomaly_score':        anomaly_score,
            'threshold':            round(self.threshold, 6) if self.threshold else None,
            'label':                label,
            'is_anomaly':           is_anomaly,
            'trained':              True
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

class AutoencoderManager:

    def __init__(self):
        self.models = {}
        for server in Config.SERVERS:
            self.models[server['id']] = AutoencoderModel(server['id'])


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
            print(f"  Training Autoencoder for {server_id}...")
            if model.train():
                trained_count += 1
        return trained_count


# ══════════════════════════════════════════════════════════════════════════════
#  RUN DIRECTLY — Test the model
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    from database import init_db
    from collector import CollectionEngine

    print("=== InfraGuard AI — Autoencoder Test ===\n")
    init_db()

    # ── Step 1: Generate training data ───────────────────────────────────────
    print("Step 1: Generating training data (60 readings)...")
    engine = CollectionEngine()
    for i in range(60):
        engine.collect_all()
    print("  ✅ Training data ready\n")

    # ── Step 2: Train autoencoder ─────────────────────────────────────────────
    print("Step 2: Training Autoencoder for web_server_1...")
    print("  (Takes 15–30 seconds)")
    model   = AutoencoderModel('web_server_1')
    success = model.train()
    print(f"  ✅ Trained: {success}")
    print(f"  Anomaly threshold set at: {round(model.threshold, 6)}\n")

    # ── Step 3: Score normal data ─────────────────────────────────────────────
    print("Step 3: Normal metrics (expect low reconstruction error)")
    normal = {
        'cpu': 38.0, 'ram': 52.0, 'disk': 40.0,
        'network_in': 25.0, 'network_out': 18.0,
        'temperature': 53.0, 'response_time': 180.0, 'error_rate': 0.4
    }
    result = model.predict(normal)
    print(f"  Reconstruction Error : {result['reconstruction_error']}")
    print(f"  Anomaly Score        : {result['anomaly_score']}")
    print(f"  Label                : {result['label']}")
    print(f"  Is Anomaly           : {result['is_anomaly']}\n")

    # ── Step 4: Score anomalous data ──────────────────────────────────────────
    print("Step 4: Anomalous metrics (expect high reconstruction error)")
    anomalous = {
        'cpu': 97.0, 'ram': 96.0, 'disk': 94.0,
        'network_in': 999.0, 'network_out': 999.0,
        'temperature': 89.0, 'response_time': 4500.0, 'error_rate': 20.0
    }
    result = model.predict(anomalous)
    print(f"  Reconstruction Error : {result['reconstruction_error']}")
    print(f"  Anomaly Score        : {result['anomaly_score']}")
    print(f"  Label                : {result['label']}")
    print(f"  Is Anomaly           : {result['is_anomaly']}\n")

    # ── Step 5: Train and score all servers ───────────────────────────────────
    print("Step 5: Training all 9 servers and scoring latest data")
    print("  (This will take 2–4 minutes — training 9 neural networks)\n")
    manager = AutoencoderManager()
    trained = manager.train_all()
    print(f"\n  ✅ Trained {trained}/9 models\n")

    engine.collect_all()
    latest  = engine.get_latest()
    results = manager.predict_all(latest)

    print("\nResults:")
    for server in Config.SERVERS:
        sid = server['id']
        r   = results.get(sid, {})
        if r:
            score = r.get('anomaly_score', 0)
            label = r.get('label', 'Unknown')
            icon  = '🔴' if score >= 0.6 else ('🟡' if score >= 0.4 else '🟢')
            print(f"  {icon} {server['name']:20} Score: {score:.4f}  →  {label}")

    print("\n✅ Autoencoder test complete!")