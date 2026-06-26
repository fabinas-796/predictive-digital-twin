# alert_engine.py — Alert Management Engine for InfraGuard AI

from database import (
    create_alert, get_active_alerts, resolve_alert,
    auto_resolve_alerts, get_latest_metric, init_db
)
from config import Config


# ══════════════════════════════════════════════════════════════════════════════
#  CORE — Check one server's metrics and fire alerts if needed
# ══════════════════════════════════════════════════════════════════════════════

def check_server(server_id, data):
    """
    Given a dict of metrics for one server, check every metric
    against thresholds and create or resolve alerts as needed.
    """
    thresholds = Config.ALERT_THRESHOLDS

    # List of (metric_key, display_label, unit)
    checks = [
        ('cpu',           'CPU Usage',       '%'),
        ('ram',           'RAM Usage',       '%'),
        ('disk',          'Disk Usage',      '%'),
        ('temperature',   'Temperature',     '°C'),
        ('error_rate',    'Error Rate',      '%'),
        ('response_time', 'Response Time',   'ms'),
    ]

    for metric, label, unit in checks:
        value = data.get(metric)
        if value is None:
            continue

        limits = thresholds.get(metric)
        if not limits:
            continue

        # Determine severity — check from highest to lowest
        severity = None
        threshold_value = None

        if value >= limits['critical']:
            severity        = 'CRITICAL'
            threshold_value = limits['critical']
        elif value >= limits['high']:
            severity        = 'HIGH'
            threshold_value = limits['high']
        elif value >= limits['warning']:
            severity        = 'WARNING'
            threshold_value = limits['warning']

        if severity:
            # Build a human-readable message
            message = (
                f"{label} is {severity.lower()} on this server: "
                f"{value:.1f}{unit} (threshold: {threshold_value}{unit})"
            )
            create_alert(server_id, severity, metric, message, value, threshold_value)
        else:
            # Metric is back to normal — auto-resolve any existing alert
            auto_resolve_alerts(server_id, metric)


# ══════════════════════════════════════════════════════════════════════════════
#  BULK CHECK — Run check on all servers at once
# ══════════════════════════════════════════════════════════════════════════════

def check_all_servers(latest_data):
    """
    Pass in the full latest_data dict from CollectionEngine.get_latest()
    and check every server.
    Returns count of new alerts created this round.
    """
    if not latest_data:
        return 0

    alerts_before = len(get_active_alerts())

    for server_id, data in latest_data.items():
        check_server(server_id, data)

    alerts_after = len(get_active_alerts())
    new_alerts   = max(0, alerts_after - alerts_before)
    return new_alerts


# ══════════════════════════════════════════════════════════════════════════════
#  SUMMARY — Useful for dashboard overview
# ══════════════════════════════════════════════════════════════════════════════

def get_alert_summary():
    """
    Returns a dict with counts per severity for the dashboard header.
    Example: {'CRITICAL': 1, 'HIGH': 2, 'WARNING': 5, 'total': 8}
    """
    alerts = get_active_alerts()
    summary = {'CRITICAL': 0, 'HIGH': 0, 'WARNING': 0, 'INFO': 0, 'total': 0}

    for a in alerts:
        sev = a.get('severity', 'INFO')
        if sev in summary:
            summary[sev] += 1
        summary['total'] += 1

    return summary


def get_server_risk_level(server_id):
    """
    Returns the highest active alert severity for a server.
    Used to colour-code servers on the dashboard.
    Returns: 'CRITICAL' / 'HIGH' / 'WARNING' / 'OK'
    """
    alerts = get_active_alerts()
    server_alerts = [a for a in alerts if a['server_id'] == server_id]

    if not server_alerts:
        return 'OK'

    priority = {'CRITICAL': 4, 'HIGH': 3, 'WARNING': 2, 'INFO': 1}
    highest  = max(server_alerts, key=lambda a: priority.get(a['severity'], 0))
    return highest['severity']


# ══════════════════════════════════════════════════════════════════════════════
#  RUN DIRECTLY — Test the alert engine
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("=== InfraGuard AI — Alert Engine Test ===\n")
    init_db()

    # ── Test 1: normal metrics → no alerts ───────────────────────────────────
    print("Test 1: Normal metrics (should create 0 alerts)")
    normal_data = {
        'cpu': 45.0, 'ram': 60.0, 'disk': 50.0,
        'temperature': 55.0, 'error_rate': 0.5, 'response_time': 200.0
    }
    check_server('web_server_1', normal_data)
    summary = get_alert_summary()
    print(f"  Active alerts: {summary['total']} ✅\n")

    # ── Test 2: high metrics → alerts fire ───────────────────────────────────
    print("Test 2: High metrics (should create alerts)")
    high_data = {
        'cpu': 96.0,          # → CRITICAL
        'ram': 87.0,          # → HIGH
        'disk': 72.0,         # → WARNING
        'temperature': 80.0,  # → HIGH
        'error_rate': 0.5,
        'response_time': 200.0
    }
    check_server('app_server', high_data)
    summary = get_alert_summary()
    print(f"  Active alerts: {summary['total']}")
    print(f"  CRITICAL: {summary['CRITICAL']}  HIGH: {summary['HIGH']}  WARNING: {summary['WARNING']}\n")

    # ── Test 3: show alert details ────────────────────────────────────────────
    print("Test 3: Alert details")
    for alert in get_active_alerts():
        print(f"  [{alert['severity']:8}] {alert['server_name']:20} | {alert['metric']:15} | {alert['message'][:50]}")

    # ── Test 4: duplicate check ───────────────────────────────────────────────
    print("\nTest 4: Duplicate check (firing same alerts again)")
    before = get_alert_summary()['total']
    check_server('app_server', high_data)
    after  = get_alert_summary()['total']
    print(f"  Alerts before: {before}  After: {after}  (should be same — no duplicates) ✅")

    # ── Test 5: auto-resolve ──────────────────────────────────────────────────
    print("\nTest 5: Metrics return to normal → auto-resolve")
    check_server('app_server', normal_data)
    summary = get_alert_summary()
    print(f"  Active alerts after recovery: {summary['total']} (app_server alerts resolved) ✅")

    # ── Test 6: server risk level ─────────────────────────────────────────────
    print("\nTest 6: Server risk levels")
    from config import Config
    for server in Config.SERVERS:
        risk = get_server_risk_level(server['id'])
        icon = {'CRITICAL':'🔴','HIGH':'🟠','WARNING':'🟡','OK':'🟢'}.get(risk,'⚪')
        print(f"  {icon} {server['name']:20} → {risk}")

    print("\n✅ Alert engine test complete!")