# app.py — Main Flask Server for InfraGuard AI

import warnings
warnings.filterwarnings('ignore')

import os
import json
import threading
import time
from datetime import datetime
from flask import Flask, render_template, jsonify, request, session, redirect, url_for

from config import Config
from database import (
    init_db, get_all_servers, get_metric_history, get_latest_metric,
    get_active_alerts, get_all_alerts, acknowledge_alert, resolve_alert,
    get_latest_prediction, get_all_users, verify_user, save_metric,
    get_metric_count, add_server, delete_server, server_exists
)
from collector import CollectionEngine
from alert_engine import check_all_servers, get_alert_summary, get_server_risk_level
from report_engine import register_report_routes, generate_csv, PDFReportGenerator


# ══════════════════════════════════════════════════════════════════════════════
#  APP SETUP
# ══════════════════════════════════════════════════════════════════════════════

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

# Global engine instances
collector       = None
pred_engine     = None
engines_started = False


def start_engines():
    """Start collector and prediction engine in background."""
    global collector, pred_engine, engines_started

    if engines_started:
        return

    print("\n[InfraGuard] Starting data collection engine...")
    collector = CollectionEngine()
    collector.start()

    print("[InfraGuard] Loading AI prediction engine...")
    try:
        from models.prediction_engine import PredictionEngine
        pred_engine = PredictionEngine()
        print("[InfraGuard] AI engine ready ✅")
    except Exception as e:
        print(f"[InfraGuard] AI engine warning: {e}")
        pred_engine = None

    engines_started = True

    # Background thread that runs predictions every 15 seconds
    def prediction_loop():
        while True:
            try:
                if pred_engine and collector:
                    latest = collector.get_latest()
                    if latest:
                        pred_engine.predict_all(latest)
                        # Also run alert checks
                        check_all_servers(latest)
            except Exception as e:
                print(f"[PredictionLoop Error] {e}")
            time.sleep(15)

    t = threading.Thread(target=prediction_loop, daemon=True)
    t.start()
    print("[InfraGuard] Prediction loop started ✅\n")


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def login_required(f):
    """Decorator — redirects to login if not logged in."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    return session.get('user', None)


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE ROUTES — Serve HTML pages
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login_page'))
    return redirect(url_for('overview_page'))


@app.route('/login')
def login_page():
    if 'user' in session:
        return redirect(url_for('overview_page'))
    return render_template('login.html')


@app.route('/overview')
@login_required
def overview_page():
    return render_template('index.html', user=get_current_user())


@app.route('/twin')
@login_required
def twin_page():
    return render_template('twin.html', user=get_current_user())


@app.route('/servers')
@login_required
def servers_page():
    return render_template('servers.html', user=get_current_user())


@app.route('/ai')
@login_required
def ai_page():
    return render_template('ai_models.html', user=get_current_user())


@app.route('/alerts')
@login_required
def alerts_page():
    return render_template('alerts.html', user=get_current_user())


@app.route('/reports')
@login_required
def reports_page():
    return render_template('reports.html', user=get_current_user())

@app.route('/admin')
@login_required
def admin_page():
    user = get_current_user()
    if user['role'] != 'admin':
        return redirect(url_for('overview_page'))
    return render_template('admin.html', user=user)

# ══════════════════════════════════════════════════════════════════════════════
#  AUTH API
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/login', methods=['POST'])
def api_login():
    data     = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    user = verify_user(username, password)
    if user:
        session['user'] = {
            'id':       user['id'],
            'username': user['username'],
            'role':     user['role'],
        }
        return jsonify({
            'success':  True,
            'username': user['username'],
            'role':     user['role'],
        })

    return jsonify({'success': False, 'message': 'Invalid username or password'}), 401


@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'success': True})


@app.route('/api/me')
def api_me():
    user = get_current_user()
    if not user:
        return jsonify({'logged_in': False}), 401
    return jsonify({'logged_in': True, **user})


# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD API — Overview
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/overview')
@login_required
def api_overview():
    """Main overview — system health summary + all server statuses."""
    servers  = get_all_servers()
    alerts   = get_alert_summary()
    latest   = collector.get_latest() if collector else {}

    server_list = []
    for s in servers:
        sid      = s['id']
        metrics  = latest.get(sid, {})
        risk     = get_server_risk_level(sid)
        pred     = get_latest_prediction(sid)

        server_list.append({
            'id':     sid,
            'name':   s['name'],
            'type':   s['type'],
            'status': s['status'],
            'risk':   risk,
            'metrics': {
                'cpu':           metrics.get('cpu', 0),
                'ram':           metrics.get('ram', 0),
                'disk':          metrics.get('disk', 0),
                'temperature':   metrics.get('temperature', 0),
                'response_time': metrics.get('response_time', 0),
                'error_rate':    metrics.get('error_rate', 0),
            },
            'prediction': {
                'risk_level':         pred.get('risk_level', 'LOW') if pred else 'LOW',
                'failure_probability': pred.get('failure_probability', 0) if pred else 0,
                'time_to_failure':    pred.get('time_to_failure', 'N/A') if pred else 'N/A',
            }
        })

    # Overall health score
    critical = sum(1 for s in server_list if s['risk'] == 'CRITICAL')
    high     = sum(1 for s in server_list if s['risk'] == 'HIGH')
    health   = max(0, 100 - (critical * 25) - (high * 10))

    return jsonify({
        'health':       health,
        'servers':      server_list,
        'alerts':       alerts,
        'total':        len(servers),
        'timestamp':    datetime.now().strftime('%H:%M:%S'),
    })


# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD API — Metrics
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/metrics/<server_id>')
@login_required
def api_metrics(server_id):
    """Get metric history for one server — used by charts."""
    limit   = request.args.get('limit', 50, type=int)
    history = get_metric_history(server_id, limit=limit)
    latest  = collector.get_latest(server_id) if collector else {}

    return jsonify({
        'server_id': server_id,
        'history':   history,
        'latest':    latest,
        'count':     get_metric_count(server_id),
    })


@app.route('/api/metrics/all/latest')
@login_required
def api_all_latest():
    """Get latest metrics for all servers at once."""
    latest = collector.get_latest() if collector else {}
    return jsonify(latest)


# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD API — Alerts
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/alerts')
@login_required
def api_alerts():
    """Get all alerts with optional filter."""
    status = request.args.get('status', 'all')
    if status == 'active':
        alerts = get_active_alerts()
    else:
        alerts = get_all_alerts(limit=200)

    return jsonify({
        'alerts':  alerts,
        'summary': get_alert_summary(),
        'count':   len(alerts),
    })


@app.route('/api/alerts/<int:alert_id>/acknowledge', methods=['POST'])
@login_required
def api_acknowledge_alert(alert_id):
    """Acknowledge an alert."""
    user = get_current_user()
    acknowledge_alert(alert_id, user['username'])
    return jsonify({'success': True})


@app.route('/api/alerts/<int:alert_id>/resolve', methods=['POST'])
@login_required
def api_resolve_alert(alert_id):
    """Resolve an alert."""
    resolve_alert(alert_id)
    return jsonify({'success': True})


# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD API — AI Predictions
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/predictions')
@login_required
def api_predictions():
    """Get latest predictions for all servers."""
    import json
    results = {}

    # Always load from database first — most reliable source
    for server in Config.SERVERS:
        pred = get_latest_prediction(server['id'])
        if pred:
            # Fix model_details if stored as string
            if pred.get('model_details') and isinstance(pred['model_details'], str):
                try:
                    pred['model_details'] = json.loads(pred['model_details'])
                except:
                    pass
            # Fix forecast_data if stored as string
            if pred.get('forecast_data') and isinstance(pred['forecast_data'], str):
                try:
                    pred['forecast_data'] = json.loads(pred['forecast_data'])
                except:
                    pass
            results[server['id']] = pred

    # Also check dynamically added servers
    from database import get_all_servers
    all_servers   = get_all_servers()
    config_ids    = [s['id'] for s in Config.SERVERS]
    dynamic       = [s for s in all_servers if s['id'] not in config_ids]
    for server in dynamic:
        pred = get_latest_prediction(server['id'])
        if pred:
            if pred.get('model_details') and isinstance(pred['model_details'], str):
                try:
                    pred['model_details'] = json.loads(pred['model_details'])
                except:
                    pass
            results[server['id']] = pred

    # Overlay with live engine results if available
    if pred_engine:
        live = pred_engine.get_latest()
        if live:
            results.update(live)

    return jsonify(results)


@app.route('/api/predictions/<server_id>')
@login_required
def api_prediction_server(server_id):
    """Get latest prediction for one server."""
    if pred_engine:
        result = pred_engine.get_latest(server_id)
        if result:
            return jsonify(result)

    pred = get_latest_prediction(server_id)
    return jsonify(pred or {})


# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD API — Digital Twin
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/twin')
@login_required
def api_twin():
    """Get full topology data for Digital Twin Map."""
    servers = get_all_servers()
    latest  = collector.get_latest() if collector else {}

    nodes = []
    for s in servers:
        sid     = s['id']
        metrics = latest.get(sid, {})
        risk    = get_server_risk_level(sid)

        nodes.append({
            'id':       sid,
            'name':     s['name'],
            'type':     s['type'],
            'status':   s['status'],
            'risk':     risk,
            'cpu':      metrics.get('cpu', 0),
            'ram':      metrics.get('ram', 0),
            'disk':     metrics.get('disk', 0),
        })

    # Define connections between nodes
    connections = [
        {'from': 'firewall',     'to': 'web_server_1'},
        {'from': 'firewall',     'to': 'web_server_2'},
        {'from': 'web_server_1', 'to': 'app_server'},
        {'from': 'web_server_2', 'to': 'app_server'},
        {'from': 'app_server',   'to': 'db_mysql'},
        {'from': 'app_server',   'to': 'db_redis'},
        {'from': 'app_server',   'to': 'cloud_aws'},
        {'from': 'cloud_aws',    'to': 'cdn_server'},
        {'from': 'pc_local',     'to': 'firewall'},
    ]

    return jsonify({
        'nodes':       nodes,
        'connections': connections,
        'timestamp':   datetime.now().strftime('%H:%M:%S'),
    })


# ══════════════════════════════════════════════════════════════════════════════
#  SIMULATION — Inject fake failures for demo
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/simulate/failure', methods=['POST'])
@login_required
def api_simulate_failure():
    """Inject a fake failure into a server for demo purposes."""
    user = get_current_user()
    if user['role'] not in ('admin', 'engineer'):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    data      = request.get_json()
    server_id = data.get('server_id', 'web_server_1')

    # Inject extreme metrics
    failure_data = {
        'cpu':           97.5,
        'ram':           95.2,
        'disk':          93.1,
        'network_in':    850.0,
        'network_out':   920.0,
        'temperature':   88.0,
        'response_time': 4500.0,
        'error_rate':    18.5,
    }

    save_metric(server_id, failure_data)

    # Update in-memory latest
    if collector:
        collector.latest[server_id] = {
            **failure_data,
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'server_id': server_id
        }

    # Trigger alert check
    check_all_servers({server_id: failure_data})

    return jsonify({
        'success':   True,
        'message':   f'Failure injected into {server_id}',
        'server_id': server_id,
    })


@app.route('/api/simulate/recover', methods=['POST'])
@login_required
def api_simulate_recover():
    """Recover a server from simulated failure."""
    data      = request.get_json()
    server_id = data.get('server_id', 'web_server_1')

    recovery_data = {
        'cpu':           25.0,
        'ram':           45.0,
        'disk':          40.0,
        'network_in':    20.0,
        'network_out':   15.0,
        'temperature':   52.0,
        'response_time': 150.0,
        'error_rate':    0.2,
    }

    save_metric(server_id, recovery_data)

    if collector:
        collector.latest[server_id] = {
            **recovery_data,
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'server_id': server_id
        }

    check_all_servers({server_id: recovery_data})

    return jsonify({
        'success':   True,
        'message':   f'{server_id} recovered',
        'server_id': server_id,
    })


# ══════════════════════════════════════════════════════════════════════════════
#  REPORTS API
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/reports/data')
@login_required
def api_report_data():
    """Get data needed to generate reports."""
    servers  = get_all_servers()
    alerts   = get_all_alerts(limit=50)
    latest   = collector.get_latest() if collector else {}

    report_data = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'servers':      [],
        'alerts':       alerts[:10],
        'summary': {
            'total_servers':  len(servers),
            'total_alerts':   len(alerts),
            'critical_alerts': sum(1 for a in alerts if a['severity'] == 'CRITICAL'),
        }
    }

    for s in servers:
        sid     = s['id']
        metrics = latest.get(sid, {})
        pred    = get_latest_prediction(sid)
        report_data['servers'].append({
            'id':     sid,
            'name':   s['name'],
            'type':   s['type'],
            'status': s['status'],
            'cpu':    metrics.get('cpu', 0),
            'ram':    metrics.get('ram', 0),
            'disk':   metrics.get('disk', 0),
            'risk':   pred.get('risk_level', 'LOW') if pred else 'LOW',
        })

    return jsonify(report_data)


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN API
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/admin/users')
@login_required
def api_admin_users():
    """Get all users — admin only."""
    user = get_current_user()
    if user['role'] != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    return jsonify(get_all_users())

@app.route('/api/admin/servers/add', methods=['POST'])
@login_required
def api_add_server():
    """Add a new dynamic server — admin only."""
    user = get_current_user()
    if user['role'] != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    data        = request.get_json()
    server_id   = data.get('server_id',   '').strip().lower().replace(' ', '_')
    server_name = data.get('server_name', '').strip()
    server_type = data.get('server_type', 'web').strip()

    # Validate
    if not server_id or not server_name:
        return jsonify({'success': False, 'message': 'Server ID and name are required'}), 400

    if server_exists(server_id):
        return jsonify({'success': False, 'message': f'Server ID "{server_id}" already exists'}), 400

    valid_types = ['web', 'application', 'database', 'cache', 'cloud', 'cdn', 'network']
    if server_type not in valid_types:
        server_type = 'web'

    # Add to database
    success = add_server(server_id, server_name, server_type)
    if not success:
        return jsonify({'success': False, 'message': 'Database error'}), 500

    # Add to running collector
    if collector:
        collector.add_server(server_id, server_type)

    return jsonify({
        'success':     True,
        'message':     f'Server "{server_name}" added successfully',
        'server_id':   server_id,
        'server_name': server_name,
        'server_type': server_type,
    })


@app.route('/api/admin/servers/delete', methods=['POST'])
@login_required
def api_delete_server():
    """Delete a dynamic server — admin only."""
    user = get_current_user()
    if user['role'] != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    data      = request.get_json()
    server_id = data.get('server_id', '').strip()

    # Prevent deleting original servers
    original_ids = [s['id'] for s in Config.SERVERS]
    if server_id in original_ids:
        return jsonify({
            'success': False,
            'message': 'Cannot delete original servers — only custom servers can be removed'
        }), 400

    # Remove from collector
    if collector:
        collector.remove_server(server_id)

    # Remove from database
    success = delete_server(server_id)
    if not success:
        return jsonify({'success': False, 'message': 'Database error'}), 500

    return jsonify({
        'success':   True,
        'message':   f'Server "{server_id}" deleted successfully',
        'server_id': server_id,
    })


@app.route('/api/admin/servers')
@login_required
def api_admin_servers():
    """Get all servers including dynamic ones — admin only."""
    user = get_current_user()
    if user['role'] != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    servers     = get_all_servers()
    original_ids= [s['id'] for s in Config.SERVERS]
    latest      = collector.get_latest() if collector else {}

    result = []
    for s in servers:
        metrics = latest.get(s['id'], {})
        result.append({
            'id':         s['id'],
            'name':       s['name'],
            'type':       s['type'],
            'status':     s['status'],
            'is_original': s['id'] in original_ids,
            'cpu':        metrics.get('cpu',  0),
            'ram':        metrics.get('ram',  0),
            'disk':       metrics.get('disk', 0),
        })

    return jsonify(result)
# ══════════════════════════════════════════════════════════════════════════════
#  STARTUP
# ══════════════════════════════════════════════════════════════════════════════
# Register report download routes
register_report_routes(
    app,
    get_login_required = lambda: login_required,
    get_collector      = lambda: collector
)
if __name__ == '__main__':
    print("=" * 55)
    print("   InfraGuard AI — Starting Server")
    print("=" * 55)

    # Initialize database
    init_db()

    # Start all engines
    start_engines()

    print("\n[InfraGuard] Dashboard available at:")
    print("   http://localhost:5000")
    print("\n[InfraGuard] Login credentials:")
    print("   admin    / admin123")
    print("   engineer / eng123")
    print("   viewer   / view123")
    print()

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,    # False so background threads work properly
        use_reloader=False
    )