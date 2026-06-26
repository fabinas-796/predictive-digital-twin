# database.py — All database operations for InfraGuard AI

import sqlite3
import json
import hashlib
from datetime import datetime
from config import Config


# ── Helper: hash a password ────────────────────────────────────────────────────
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# ── Helper: get a database connection ─────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row   # lets us access columns by name
    return conn


# ══════════════════════════════════════════════════════════════════════════════
#  SETUP — Create all 6 tables
# ══════════════════════════════════════════════════════════════════════════════

def init_db():
    """Create all tables and insert default data. Safe to run multiple times."""
    conn = get_db()
    c = conn.cursor()

    # ── Table 1: users ────────────────────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT UNIQUE NOT NULL,
            password    TEXT NOT NULL,
            role        TEXT NOT NULL DEFAULT 'viewer',
            created_at  TEXT DEFAULT (datetime('now')),
            last_login  TEXT
        )
    ''')

    # ── Table 2: servers ──────────────────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS servers (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            type        TEXT NOT NULL,
            status      TEXT DEFAULT 'online',
            added_at    TEXT DEFAULT (datetime('now'))
        )
    ''')

    # ── Table 3: metrics ──────────────────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS metrics (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            server_id     TEXT NOT NULL,
            timestamp     TEXT DEFAULT (datetime('now')),
            cpu           REAL,
            ram           REAL,
            disk          REAL,
            network_in    REAL,
            network_out   REAL,
            temperature   REAL,
            processes     INTEGER,
            response_time REAL,
            error_rate    REAL,
            FOREIGN KEY (server_id) REFERENCES servers(id)
        )
    ''')

    # ── Table 4: alerts ───────────────────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            server_id   TEXT NOT NULL,
            severity    TEXT NOT NULL,
            metric      TEXT NOT NULL,
            message     TEXT NOT NULL,
            value       REAL,
            threshold   REAL,
            status      TEXT DEFAULT 'active',
            created_at  TEXT DEFAULT (datetime('now')),
            resolved_at TEXT,
            acknowledged_by TEXT,
            FOREIGN KEY (server_id) REFERENCES servers(id)
        )
    ''')

    # ── Table 5: predictions ──────────────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            server_id           TEXT NOT NULL,
            timestamp           TEXT DEFAULT (datetime('now')),
            anomaly_score       REAL,
            failure_probability REAL,
            risk_level          TEXT,
            time_to_failure     TEXT,
            forecast_data       TEXT,
            model_details       TEXT,
            FOREIGN KEY (server_id) REFERENCES servers(id)
        )
    ''')

    # ── Table 6: model_accuracy ───────────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS model_accuracy (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT DEFAULT (datetime('now')),
            model_name  TEXT NOT NULL,
            accuracy    REAL,
            details     TEXT
        )
    ''')

    conn.commit()

    # ── Seed default servers ──────────────────────────────────────────────────
    for s in Config.SERVERS:
        c.execute('''
            INSERT OR IGNORE INTO servers (id, name, type)
            VALUES (?, ?, ?)
        ''', (s['id'], s['name'], s['type']))

    # ── Seed default users ────────────────────────────────────────────────────
    for u in Config.DEFAULT_USERS:
        c.execute('''
            INSERT OR IGNORE INTO users (username, password, role)
            VALUES (?, ?, ?)
        ''', (u['username'], hash_password(u['password']), u['role']))

    conn.commit()
    conn.close()
    print("✅ Database initialized with all 6 tables.")


# ══════════════════════════════════════════════════════════════════════════════
#  METRICS — Save and retrieve server metrics
# ══════════════════════════════════════════════════════════════════════════════

def save_metric(server_id, data):
    """Save one metric reading for a server."""
    conn = get_db()
    conn.execute('''
        INSERT INTO metrics
            (server_id, cpu, ram, disk, network_in, network_out,
             temperature, processes, response_time, error_rate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        server_id,
        data.get('cpu'),
        data.get('ram'),
        data.get('disk'),
        data.get('network_in'),
        data.get('network_out'),
        data.get('temperature'),
        data.get('processes'),
        data.get('response_time'),
        data.get('error_rate'),
    ))
    conn.commit()
    conn.close()


def get_latest_metric(server_id):
    """Get the most recent reading for a server."""
    conn = get_db()
    row = conn.execute('''
        SELECT * FROM metrics
        WHERE server_id = ?
        ORDER BY timestamp DESC
        LIMIT 1
    ''', (server_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_metric_history(server_id, limit=100):
    """Get last N readings for a server (for charts)."""
    conn = get_db()
    rows = conn.execute('''
        SELECT * FROM metrics
        WHERE server_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (server_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]   # oldest first for charts


def get_metric_count(server_id):
    """How many readings do we have for a server? Used for AI retraining."""
    conn = get_db()
    count = conn.execute(
        'SELECT COUNT(*) FROM metrics WHERE server_id = ?', (server_id,)
    ).fetchone()[0]
    conn.close()
    return count


# ══════════════════════════════════════════════════════════════════════════════
#  ALERTS — Create and manage alerts
# ══════════════════════════════════════════════════════════════════════════════

def create_alert(server_id, severity, metric, message, value, threshold):
    """Create a new alert — but skip if an identical active alert exists."""
    conn = get_db()

    # Deduplication: don't create duplicate active alerts
    existing = conn.execute('''
        SELECT id FROM alerts
        WHERE server_id = ? AND metric = ? AND status = 'active'
        LIMIT 1
    ''', (server_id, metric)).fetchone()

    if existing:
        conn.close()
        return None   # already alerted, skip

    conn.execute('''
        INSERT INTO alerts (server_id, severity, metric, message, value, threshold)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (server_id, severity, metric, message, value, threshold))
    conn.commit()
    conn.close()
    return True


def get_active_alerts():
    """Get all currently active alerts."""
    conn = get_db()
    rows = conn.execute('''
        SELECT a.*, s.name as server_name
        FROM alerts a
        JOIN servers s ON a.server_id = s.id
        WHERE a.status = 'active'
        ORDER BY a.created_at DESC
    ''').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_alerts(limit=200):
    """Get full alert history."""
    conn = get_db()
    rows = conn.execute('''
        SELECT a.*, s.name as server_name
        FROM alerts a
        JOIN servers s ON a.server_id = s.id
        ORDER BY a.created_at DESC
        LIMIT ?
    ''', (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def acknowledge_alert(alert_id, username):
    """Mark alert as acknowledged."""
    conn = get_db()
    conn.execute('''
        UPDATE alerts
        SET status = 'acknowledged', acknowledged_by = ?
        WHERE id = ?
    ''', (username, alert_id))
    conn.commit()
    conn.close()


def resolve_alert(alert_id):
    """Mark alert as resolved."""
    conn = get_db()
    conn.execute('''
        UPDATE alerts
        SET status = 'resolved', resolved_at = datetime('now')
        WHERE id = ?
    ''', (alert_id,))
    conn.commit()
    conn.close()


def auto_resolve_alerts(server_id, metric):
    """Auto-resolve old alerts when metric goes back to normal."""
    conn = get_db()
    conn.execute('''
        UPDATE alerts
        SET status = 'resolved', resolved_at = datetime('now')
        WHERE server_id = ? AND metric = ? AND status = 'active'
    ''', (server_id, metric))
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
#  PREDICTIONS — Save and retrieve AI predictions
# ══════════════════════════════════════════════════════════════════════════════

def save_prediction(server_id, anomaly_score, failure_prob, risk_level,
                    time_to_failure, forecast_data=None, model_details=None):
    """Save one AI prediction for a server."""
    conn = get_db()
    conn.execute('''
        INSERT INTO predictions
            (server_id, anomaly_score, failure_probability, risk_level,
             time_to_failure, forecast_data, model_details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        server_id,
        anomaly_score,
        failure_prob,
        risk_level,
        time_to_failure,
        json.dumps(forecast_data) if forecast_data else None,
        json.dumps(model_details) if model_details else None,
    ))
    conn.commit()
    conn.close()


def get_latest_prediction(server_id):
    """Get the most recent AI prediction for a server."""
    conn = get_db()
    row = conn.execute('''
        SELECT * FROM predictions
        WHERE server_id = ?
        ORDER BY timestamp DESC
        LIMIT 1
    ''', (server_id,)).fetchone()
    conn.close()
    if not row:
        return None
    result = dict(row)
    # Decode JSON fields
    if result.get('forecast_data'):
        result['forecast_data'] = json.loads(result['forecast_data'])
    if result.get('model_details'):
        result['model_details'] = json.loads(result['model_details'])
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  USERS — For login system
# ══════════════════════════════════════════════════════════════════════════════

def get_user(username):
    """Find a user by username."""
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM users WHERE username = ?', (username,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def verify_user(username, password):
    """Check if username + password are correct. Returns user dict or None."""
    user = get_user(username)
    if user and user['password'] == hash_password(password):
        # Update last login time
        conn = get_db()
        conn.execute(
            "UPDATE users SET last_login = datetime('now') WHERE username = ?",
            (username,)
        )
        conn.commit()
        conn.close()
        return user
    return None


def get_all_users():
    """Get all users (for Admin panel)."""
    conn = get_db()
    rows = conn.execute(
        'SELECT id, username, role, created_at, last_login FROM users'
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
#  SERVERS — Status updates
# ══════════════════════════════════════════════════════════════════════════════

def get_all_servers():
    """Get all server definitions."""
    conn = get_db()
    rows = conn.execute('SELECT * FROM servers').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_server_status(server_id, status):
    """Update a server's status: online / warning / critical / offline."""
    conn = get_db()
    conn.execute(
        'UPDATE servers SET status = ? WHERE id = ?', (status, server_id)
    )
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
#  RUN DIRECTLY — Test the database
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("Initializing InfraGuard AI database...")
    init_db()

    print("\n--- Servers in database ---")
    for s in get_all_servers():
        print(f"  {s['id']:15} | {s['name']:20} | {s['type']}")

    print("\n--- Users in database ---")
    for u in get_all_users():
        print(f"  {u['username']:12} | role: {u['role']}")

    print("\n✅ All done! Database is ready.")

def add_server(server_id, name, server_type):
    """Add a new server to the database."""
    conn = get_db()
    try:
        conn.execute('''
            INSERT INTO servers (id, name, type, status)
            VALUES (?, ?, ?, 'online')
        ''', (server_id, name, server_type))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        print(f"[add_server error] {e}")
        return False


def delete_server(server_id):
    """Delete a server and all its data from the database."""
    conn = get_db()
    try:
        # Delete all related data first
        conn.execute('DELETE FROM metrics     WHERE server_id = ?', (server_id,))
        conn.execute('DELETE FROM alerts      WHERE server_id = ?', (server_id,))
        conn.execute('DELETE FROM predictions WHERE server_id = ?', (server_id,))
        conn.execute('DELETE FROM servers     WHERE id = ?',        (server_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        print(f"[delete_server error] {e}")
        return False


def server_exists(server_id):
    """Check if a server ID already exists."""
    conn = get_db()
    row  = conn.execute(
        'SELECT id FROM servers WHERE id = ?', (server_id,)
    ).fetchone()
    conn.close()
    return row is not None