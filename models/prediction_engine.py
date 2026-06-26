# models/prediction_engine.py — Combines all 4 AI models for InfraGuard AI

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings
warnings.filterwarnings('ignore')

from datetime import datetime
from database import save_prediction, get_metric_history, init_db
from config import Config

from models.isolation_forest import IsolationForestManager
from models.random_forest    import RandomForestManager
from models.lstm_model       import LSTMManager
from models.autoencoder      import AutoencoderManager


# ══════════════════════════════════════════════════════════════════════════════
#  WEIGHTS — how much each model contributes to final score
# ══════════════════════════════════════════════════════════════════════════════

MODEL_WEIGHTS = {
    'isolation_forest': 0.25,
    'random_forest':    0.35,
    'lstm':             0.20,
    'autoencoder':      0.20,
}


# ══════════════════════════════════════════════════════════════════════════════
#  PREDICTION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class PredictionEngine:
    """
    Combines all 4 AI models into one unified prediction per server.
    Runs automatically alongside the data collector.
    """

    def __init__(self):
        print("  [PredictionEngine] Loading all 4 models...")
        self.if_manager  = IsolationForestManager()
        self.rf_manager  = RandomForestManager()
        self.lstm_manager= LSTMManager()
        self.ae_manager  = AutoencoderManager()
        self.last_results= {}   # cache of latest predictions
        print("  [PredictionEngine] All models loaded ✅")


    # ── Predict one server ────────────────────────────────────────────────────

    def predict_server(self, server_id, metric_data):
        """
        Run all 4 models on one server and combine into unified result.
        Returns a rich dict with all model outputs + combined score.
        """

        # ── Run each model ────────────────────────────────────────────────────
        if_result  = self.if_manager.predict(server_id, metric_data)  or {}
        rf_result  = self.rf_manager.predict(server_id, metric_data)  or {}
        lstm_result= self.lstm_manager.forecast(server_id, metric_data) or {}
        ae_result  = self.ae_manager.predict(server_id, metric_data)  or {}

        # ── Extract scores ────────────────────────────────────────────────────
        if_score  = float(if_result.get('anomaly_score', 0))
        rf_score  = float(rf_result.get('failure_probability', 0)) / 100.0
        ae_score  = float(ae_result.get('anomaly_score', 0))

        # LSTM contributes via time-to-failure urgency
        lstm_score = self._lstm_urgency_score(lstm_result)

        # ── Weighted combination ──────────────────────────────────────────────
        combined = (
            if_score   * MODEL_WEIGHTS['isolation_forest'] +
            rf_score   * MODEL_WEIGHTS['random_forest']    +
            lstm_score * MODEL_WEIGHTS['lstm']             +
            ae_score   * MODEL_WEIGHTS['autoencoder']
        )
        combined = round(min(1.0, max(0.0, combined)), 4)

        # ── Risk level ────────────────────────────────────────────────────────
        risk_level = self._score_to_risk(combined)

        # ── Time to failure ───────────────────────────────────────────────────
        time_to_failure = lstm_result.get(
            'time_to_failure', 'No failure predicted in next 30 minutes'
        )

        # ── Which model is most concerned ─────────────────────────────────────
        model_scores = {
            'isolation_forest': round(if_score  * 100, 1),
            'random_forest':    round(rf_score  * 100, 1),
            'lstm':             round(lstm_score* 100, 1),
            'autoencoder':      round(ae_score  * 100, 1),
        }
        top_model = max(model_scores, key=model_scores.get)

        # ── Build final result ────────────────────────────────────────────────
        result = {
            'server_id':          server_id,
            'timestamp':          datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'combined_score':     round(combined * 100, 2),   # as %
            'risk_level':         risk_level,
            'time_to_failure':    time_to_failure,
            'top_concern':        top_model,

            # Individual model results
            'isolation_forest': {
                'score': round(if_score * 100, 2),
                'label': if_result.get('label', 'N/A'),
            },
            'random_forest': {
                'score':              round(rf_score * 100, 2),
                'risk_level':         rf_result.get('risk_level', 'N/A'),
                'top_reason':         rf_result.get('top_reason', 'N/A'),
                'feature_importance': rf_result.get('feature_importance', {}),
            },
            'lstm': {
                'score':          round(lstm_score * 100, 2),
                'cpu_forecast':   lstm_result.get('cpu_forecast', []),
                'ram_forecast':   lstm_result.get('ram_forecast', []),
                'method':         lstm_result.get('method', 'N/A'),
            },
            'autoencoder': {
                'score':               round(ae_score * 100, 2),
                'label':               ae_result.get('label', 'N/A'),
                'reconstruction_error':ae_result.get('reconstruction_error', 0),
            },
        }

        return result


    # ── Predict all servers ───────────────────────────────────────────────────

    def predict_all(self, latest_data):
        """
        Run predictions for all servers.
        Saves results to database and caches in memory.
        Returns dict of { server_id: result }
        """
        results = {}

        for server_id, metric_data in latest_data.items():
            try:
                result = self.predict_server(server_id, metric_data)
                results[server_id] = result

                # Save to database
                save_prediction(
                    server_id       = server_id,
                    anomaly_score   = result['isolation_forest']['score'] / 100,
                    failure_prob    = result['random_forest']['score'],
                    risk_level      = result['risk_level'],
                    time_to_failure = result['time_to_failure'],
                    forecast_data   = {
                        'cpu': result['lstm']['cpu_forecast'],
                        'ram': result['lstm']['ram_forecast'],
                    },
                    model_details   = {
                        'combined_score':  result['combined_score'],
                        'top_concern':     result['top_concern'],
                        'model_scores':    {
                            'isolation_forest': result['isolation_forest']['score'],
                            'random_forest':    result['random_forest']['score'],
                            'lstm':             result['lstm']['score'],
                            'autoencoder':      result['autoencoder']['score'],
                        }
                    }
                )

            except Exception as e:
                print(f"  [PredictionEngine] Error on {server_id}: {e}")

        self.last_results = results
        return results


    def get_latest(self, server_id=None):
        """Return cached latest predictions."""
        if server_id:
            return self.last_results.get(server_id)
        return self.last_results


    # ── Helper methods ────────────────────────────────────────────────────────

    def _lstm_urgency_score(self, lstm_result):
        """
        Convert LSTM time-to-failure into a 0–1 urgency score.
        Imminent failure = high score, no failure = low score.
        """
        ttf = lstm_result.get('time_to_failure', '')
        if not ttf or 'No failure' in ttf:
            return 0.05   # tiny baseline score

        if 'IMMINENT' in ttf:
            return 0.95
        if 'SOON' in ttf:
            return 0.65

        # Extract minutes from string like "~18 minutes"
        try:
            minutes = int(''.join(filter(str.isdigit, ttf.split('minutes')[0])))
            if minutes <= 10:
                return 0.90
            elif minutes <= 20:
                return 0.60
            else:
                return 0.30
        except Exception:
            return 0.10


    def _score_to_risk(self, score):
        """Convert combined 0–1 score to risk level label."""
        if score >= 0.75:
            return 'CRITICAL'
        elif score >= 0.50:
            return 'HIGH'
        elif score >= 0.25:
            return 'MEDIUM'
        else:
            return 'LOW'


    def get_system_summary(self):
        """
        Returns a high-level summary of the entire infrastructure.
        Used by the dashboard Overview page.
        """
        if not self.last_results:
            return {
                'total_servers':    len(Config.SERVERS),
                'healthy':          len(Config.SERVERS),
                'at_risk':          0,
                'critical':         0,
                'overall_health':   100,
                'highest_risk':     None,
            }

        counts = {'LOW': 0, 'MEDIUM': 0, 'HIGH': 0, 'CRITICAL': 0}
        highest_score  = 0
        highest_server = None

        for server_id, result in self.last_results.items():
            risk = result.get('risk_level', 'LOW')
            counts[risk] = counts.get(risk, 0) + 1

            score = result.get('combined_score', 0)
            if score > highest_score:
                highest_score  = score
                highest_server = server_id

        total    = len(self.last_results)
        at_risk  = counts['HIGH'] + counts['CRITICAL']
        healthy  = counts['LOW']  + counts['MEDIUM']

        # Overall health = 100 minus weighted penalty
        penalty       = (counts['CRITICAL'] * 25 + counts['HIGH'] * 10 +
                         counts['MEDIUM']   * 3)
        overall_health= max(0, 100 - penalty)

        return {
            'total_servers':  total,
            'healthy':        healthy,
            'at_risk':        at_risk,
            'critical':       counts['CRITICAL'],
            'overall_health': overall_health,
            'highest_risk':   highest_server,
            'risk_counts':    counts,
        }


# ══════════════════════════════════════════════════════════════════════════════
#  RUN DIRECTLY — Full system test
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    from collector import CollectionEngine

    print("=" * 55)
    print("  InfraGuard AI — Full Prediction Engine Test")
    print("=" * 55)
    print()
    init_db()

    # ── Step 1: Generate data ─────────────────────────────────────────────────
    print("Step 1: Generating training data (80 readings)...")
    collector = CollectionEngine()
    for i in range(80):
        collector.collect_all()
    print("  ✅ Done\n")

    # ── Step 2: Load prediction engine ───────────────────────────────────────
    print("Step 2: Loading prediction engine (all 4 models)...")
    engine = PredictionEngine()
    print()

    # ── Step 3: Run predictions on all servers ────────────────────────────────
    print("Step 3: Running predictions on all 9 servers...")
    collector.collect_all()
    latest  = collector.get_latest()
    results = engine.predict_all(latest)
    print("  ✅ Predictions complete\n")

    # ── Step 4: Display results ───────────────────────────────────────────────
    print("Step 4: Results — All 9 Servers")
    print(f"  {'Server':<22} {'Risk':<10} {'Score':>6}  {'IF':>6} {'RF':>6} {'LSTM':>6} {'AE':>6}  TTF")
    print(f"  {'─'*90}")

    for server in Config.SERVERS:
        sid = server['id']
        r   = results.get(sid)
        if not r:
            continue

        risk  = r['risk_level']
        score = r['combined_score']
        if_s  = r['isolation_forest']['score']
        rf_s  = r['random_forest']['score']
        ls_s  = r['lstm']['score']
        ae_s  = r['autoencoder']['score']
        ttf   = r['time_to_failure'][:35] if r['time_to_failure'] else 'N/A'

        icon  = {'CRITICAL':'🔴','HIGH':'🟠','MEDIUM':'🟡','LOW':'🟢'}.get(risk,'⚪')
        print(f"  {icon} {server['name']:<20} {risk:<10} {score:>5.1f}%"
              f"  {if_s:>5.1f} {rf_s:>5.1f} {ls_s:>5.1f} {ae_s:>5.1f}"
              f"  {ttf}")

    # ── Step 5: System summary ────────────────────────────────────────────────
    print()
    print("Step 5: System Summary")
    summary = engine.get_system_summary()
    print(f"  Total Servers  : {summary['total_servers']}")
    print(f"  Healthy        : {summary['healthy']}")
    print(f"  At Risk        : {summary['at_risk']}")
    print(f"  Critical       : {summary['critical']}")
    print(f"  Overall Health : {summary['overall_health']}%")
    print(f"  Highest Risk   : {summary['highest_risk']}")

    # ── Step 6: Deep dive one server ─────────────────────────────────────────
    print()
    print("Step 6: Deep dive — app_server")
    r = results.get('app_server', {})
    if r:
        print(f"  Combined Score     : {r['combined_score']}%")
        print(f"  Risk Level         : {r['risk_level']}")
        print(f"  Top Concern        : {r['top_concern']}")
        print(f"  Time to Failure    : {r['time_to_failure']}")
        print(f"  IF Anomaly Label   : {r['isolation_forest']['label']}")
        print(f"  RF Top Reason      : {r['random_forest']['top_reason']}")
        print(f"  AE Label           : {r['autoencoder']['label']}")
        print(f"  CPU Forecast (next 30min): {r['lstm']['cpu_forecast']}")

    print()
    print("✅ Prediction engine test complete!")
    print("   All 4 models working together successfully.")