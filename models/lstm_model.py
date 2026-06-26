# models/lstm_model.py — Model 3: Time Series Forecasting for InfraGuard AI

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
#  LSTM MODEL CLASS
# ══════════════════════════════════════════════════════════════════════════════

class LSTMModel:
    """
    Forecasts future CPU and RAM values using an LSTM neural network.
    Falls back to linear trend projection if not enough data.
    """

    def __init__(self, server_id):
        self.server_id       = server_id
        self.model           = None
        self.scaler          = MinMaxScaler()
        self.is_trained      = False
        self.sequence_length = Config.LSTM_SEQUENCE_LENGTH   # 20 readings
        self.forecast_steps  = 10   # forecast 10 steps = ~30 minutes
        self.min_samples     = 60   # need at least 60 readings to train
        self.features        = ['cpu', 'ram', 'response_time', 'error_rate']


    def _prepare_sequences(self, data):
        """
        Convert flat list of readings into (X, y) sequences for LSTM.
        X = last 20 readings, y = next reading
        """
        X, y = [], []
        for i in range(len(data) - self.sequence_length):
            X.append(data[i : i + self.sequence_length])
            y.append(data[i + self.sequence_length])
        return np.array(X), np.array(y)


    def _load_data(self):
        """Load and scale metric history."""
        history = get_metric_history(self.server_id, limit=500)
        if len(history) < self.min_samples:
            return None

        # Extract only the features we need
        raw = []
        for row in history:
            raw.append([
                float(row.get(f, 0) or 0)
                for f in self.features
            ])

        return np.array(raw)


    def train(self):
        """Build and train the LSTM model."""
        try:
            # Import TensorFlow here so startup is faster
            from tensorflow.keras.models import Sequential
            from tensorflow.keras.layers import LSTM, Dense, Dropout
            from tensorflow.keras.optimizers import Adam

            raw = self._load_data()
            if raw is None:
                return False

            # Scale to 0–1 range (LSTM works better with normalized data)
            scaled = self.scaler.fit_transform(raw)

            # Build sequences
            X, y = self._prepare_sequences(scaled)
            if len(X) < 10:
                return False

            # Build LSTM architecture
            n_features = len(self.features)
            self.model = Sequential([
                LSTM(64, return_sequences=True,
                     input_shape=(self.sequence_length, n_features)),
                Dropout(0.2),
                LSTM(32, return_sequences=False),
                Dropout(0.2),
                Dense(n_features)
            ])

            self.model.compile(
                optimizer=Adam(learning_rate=0.001),
                loss='mse'
            )

            # Train — verbose=0 means no progress spam
            self.model.fit(
                X, y,
                epochs=20,
                batch_size=16,
                validation_split=0.1,
                verbose=0
            )

            self.is_trained = True
            return True

        except Exception as e:
            print(f"  [LSTM Train Error] {e}")
            return False


    def forecast(self, metric_data=None):
        """
        Forecast the next 30 minutes of CPU and RAM.
        Uses LSTM if trained, otherwise uses linear trend projection.
        Returns dict with forecast arrays and time-to-failure estimate.
        """
        history = get_metric_history(self.server_id, limit=100)

        if len(history) < 5:
            return self._empty_forecast()

        # Try LSTM forecast first
        if self.is_trained and self.model is not None:
            try:
                return self._lstm_forecast(history)
            except Exception as e:
                print(f"  [LSTM Forecast Error] {e} — falling back to trend")

        # Fallback: linear trend projection
        return self._trend_forecast(history)


    def _lstm_forecast(self, history):
        """Use the trained LSTM to forecast future values."""
        raw = np.array([
            [float(row.get(f, 0) or 0) for f in self.features]
            for row in history
        ])

        scaled = self.scaler.transform(raw)

        # Use last `sequence_length` readings as seed
        if len(scaled) < self.sequence_length:
            return self._trend_forecast(history)

        sequence = scaled[-self.sequence_length:].copy()
        predictions = []

        # Iteratively forecast one step at a time
        for _ in range(self.forecast_steps):
            X = sequence.reshape(1, self.sequence_length, len(self.features))
            next_pred = self.model.predict(X, verbose=0)[0]
            predictions.append(next_pred)
            # Slide window forward
            sequence = np.vstack([sequence[1:], next_pred])

        # Inverse scale back to real values
        predictions       = np.array(predictions)
        predictions_real  = self.scaler.inverse_transform(predictions)

        cpu_forecast  = [round(float(v), 2) for v in predictions_real[:, 0]]
        ram_forecast  = [round(float(v), 2) for v in predictions_real[:, 1]]
        rt_forecast   = [round(float(v), 2) for v in predictions_real[:, 2]]

        # Clamp to valid ranges
        cpu_forecast = [max(0, min(100, v)) for v in cpu_forecast]
        ram_forecast = [max(0, min(100, v)) for v in ram_forecast]

        time_to_failure = self._estimate_time_to_failure(cpu_forecast, ram_forecast)

        return {
            'cpu_forecast':      cpu_forecast,
            'ram_forecast':      ram_forecast,
            'rt_forecast':       rt_forecast,
            'time_to_failure':   time_to_failure,
            'forecast_minutes':  [i * 3 for i in range(1, self.forecast_steps + 1)],
            'method':            'LSTM'
        }


    def _trend_forecast(self, history):
        """
        Simple linear trend projection — used when LSTM isn't trained yet.
        Looks at the slope of recent readings and projects forward.
        """
        recent = history[-20:] if len(history) >= 20 else history

        cpu_values = [float(r.get('cpu', 0) or 0) for r in recent]
        ram_values = [float(r.get('ram', 0) or 0) for r in recent]

        cpu_forecast = self._linear_project(cpu_values, self.forecast_steps)
        ram_forecast = self._linear_project(ram_values, self.forecast_steps)

        # Clamp
        cpu_forecast = [max(0, min(100, v)) for v in cpu_forecast]
        ram_forecast = [max(0, min(100, v)) for v in ram_forecast]

        time_to_failure = self._estimate_time_to_failure(cpu_forecast, ram_forecast)

        return {
            'cpu_forecast':     cpu_forecast,
            'ram_forecast':     ram_forecast,
            'rt_forecast':      [],
            'time_to_failure':  time_to_failure,
            'forecast_minutes': [i * 3 for i in range(1, self.forecast_steps + 1)],
            'method':           'Linear Trend'
        }


    def _linear_project(self, values, steps):
        """Project a list of values forward using linear trend."""
        if len(values) < 2:
            return [values[-1]] * steps if values else [0] * steps

        # Calculate average change per step
        changes  = [values[i+1] - values[i] for i in range(len(values)-1)]
        avg_change = sum(changes) / len(changes)

        # Dampen the trend slightly so we don't extrapolate wildly
        avg_change = avg_change * 0.8

        last  = values[-1]
        forecast = []
        for _ in range(steps):
            last += avg_change
            forecast.append(round(last, 2))

        return forecast


    def _estimate_time_to_failure(self, cpu_forecast, ram_forecast):
        """
        Given forecast arrays, estimate when (if ever) CPU or RAM
        will exceed critical threshold (90%).
        Returns a human-readable string.
        """
        critical = 90.0
        interval = 3   # each forecast step = 3 minutes

        for i, (cpu, ram) in enumerate(zip(cpu_forecast, ram_forecast)):
            if cpu >= critical or ram >= critical:
                minutes = (i + 1) * interval
                if minutes <= 10:
                    return f"~{minutes} minutes (IMMINENT)"
                elif minutes <= 20:
                    return f"~{minutes} minutes (SOON)"
                else:
                    return f"~{minutes} minutes"

        return "No failure predicted in next 30 minutes"


    def _empty_forecast(self):
        return {
            'cpu_forecast':     [],
            'ram_forecast':     [],
            'rt_forecast':      [],
            'time_to_failure':  'Insufficient data',
            'forecast_minutes': [],
            'method':           'None'
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

class LSTMManager:

    def __init__(self):
        self.models = {}
        for server in Config.SERVERS:
            self.models[server['id']] = LSTMModel(server['id'])


    def forecast(self, server_id, metric_data=None):
        if server_id not in self.models:
            return None
        return self.models[server_id].forecast(metric_data)


    def forecast_all(self, latest_data):
        results = {}
        for server_id in latest_data:
            results[server_id] = self.forecast(server_id)
        return results


    def train_all(self):
        trained_count = 0
        for server_id, model in self.models.items():
            print(f"  Training LSTM for {server_id}...")
            if model.train():
                trained_count += 1
        return trained_count


# ══════════════════════════════════════════════════════════════════════════════
#  RUN DIRECTLY — Test the model
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    from database import init_db
    from collector import CollectionEngine

    print("=== InfraGuard AI — LSTM Test ===\n")
    init_db()

    # ── Step 1: Generate training data ───────────────────────────────────────
    print("Step 1: Generating training data (80 readings)...")
    engine = CollectionEngine()
    for i in range(80):
        engine.collect_all()
    print("  ✅ Training data ready\n")

    # ── Step 2: Train LSTM for one server ────────────────────────────────────
    print("Step 2: Training LSTM for web_server_1...")
    print("  (This takes 20–40 seconds — TensorFlow is building the neural network)")
    model = LSTMModel('web_server_1')
    success = model.train()
    print(f"  ✅ Trained: {success}\n")

    # ── Step 3: Get forecast ──────────────────────────────────────────────────
    print("Step 3: Forecasting next 30 minutes for web_server_1")
    result = model.forecast()
    print(f"  Method         : {result['method']}")
    print(f"  Time to Failure: {result['time_to_failure']}")
    print(f"\n  Minute  CPU Forecast  RAM Forecast")
    print(f"  {'─'*40}")
    for i, mins in enumerate(result['forecast_minutes']):
        cpu = result['cpu_forecast'][i] if i < len(result['cpu_forecast']) else 0
        ram = result['ram_forecast'][i] if i < len(result['ram_forecast']) else 0
        cpu_bar = '█' * int(cpu / 10)
        print(f"  +{mins:2d} min   {cpu:5.1f}%  {cpu_bar}")

    # ── Step 4: Test trend fallback ───────────────────────────────────────────
    print("\nStep 4: Testing trend fallback for firewall (uses linear projection)")
    fw_model = LSTMModel('firewall')
    fw_result = fw_model.forecast()
    print(f"  Method         : {fw_result['method']}")
    print(f"  Time to Failure: {fw_result['time_to_failure']}")
    print(f"  CPU forecast   : {fw_result['cpu_forecast']}")

    # ── Step 5: All servers with trend forecast ───────────────────────────────
    print("\nStep 5: Forecasting all 9 servers")
    manager = LSTMManager()
    engine.collect_all()
    latest  = engine.get_latest()
    results = manager.forecast_all(latest)

    for server in Config.SERVERS:
        sid = server['id']
        r   = results.get(sid, {})
        if r:
            ttf    = r.get('time_to_failure', 'N/A')
            method = r.get('method', 'N/A')
            cpu_f  = r.get('cpu_forecast', [])
            peak   = max(cpu_f) if cpu_f else 0
            icon   = '🔴' if peak > 85 else ('🟡' if peak > 70 else '🟢')
            print(f"  {icon} {server['name']:20} Peak CPU: {peak:5.1f}%  TTF: {ttf}")

    print("\n✅ LSTM test complete!")