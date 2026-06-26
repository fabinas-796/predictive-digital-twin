# config.py — Central settings for InfraGuard AI

import os

class Config:
    # ── Project paths ──────────────────────────────────────
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATABASE_PATH = os.path.join(BASE_DIR, 'infraguard.db')

    # ── Flask settings ─────────────────────────────────────
    SECRET_KEY = 'infraguard-secret-key-2024'
    DEBUG = True

    # ── Data collection settings ───────────────────────────
    COLLECTION_INTERVAL = 3        # Collect data every 3 seconds
    MAX_HISTORY_RECORDS = 10000    # Keep last 10,000 readings per server

    # ── The 9 servers we will monitor ──────────────────────
    SERVERS = [
        # Real machine
        {'id': 'pc_local',      'name': 'Local PC',        'type': 'physical'},

        # Simulated servers
        {'id': 'web_server_1',  'name': 'Web Server 1',    'type': 'web'},
        {'id': 'web_server_2',  'name': 'Web Server 2',    'type': 'web'},
        {'id': 'app_server',    'name': 'App Server',      'type': 'application'},
        {'id': 'db_mysql',      'name': 'MySQL Database',  'type': 'database'},
        {'id': 'db_redis',      'name': 'Redis Cache',     'type': 'cache'},
        {'id': 'cloud_aws',     'name': 'AWS Instance',    'type': 'cloud'},
        {'id': 'cdn_server',    'name': 'CDN Server',      'type': 'cdn'},
        {'id': 'firewall',      'name': 'Firewall',        'type': 'network'},
    ]

    # ── Alert thresholds ───────────────────────────────────
    ALERT_THRESHOLDS = {
        'cpu':           {'warning': 70, 'high': 85, 'critical': 95},
        'ram':           {'warning': 70, 'high': 85, 'critical': 95},
        'disk':          {'warning': 75, 'high': 88, 'critical': 95},
        'temperature':   {'warning': 65, 'high': 75, 'critical': 85},
        'error_rate':    {'warning': 2,  'high': 5,  'critical': 10},
        'response_time': {'warning': 500,'high': 1000,'critical': 2000},
    }

    # ── AI Model settings ──────────────────────────────────
    AI_RETRAIN_EVERY = 100         # Retrain models every 100 new data points
    LSTM_SEQUENCE_LENGTH = 20      # LSTM looks at last 20 readings to predict
    FORECAST_MINUTES = 30          # Forecast 30 minutes into the future

    # ── User roles ─────────────────────────────────────────
    ROLES = {
        'admin':    {'label': 'Admin',    'level': 3},
        'engineer': {'label': 'Engineer', 'level': 2},
        'viewer':   {'label': 'Viewer',   'level': 1},
    }

    # ── Default users (we'll move to DB later) ─────────────
    DEFAULT_USERS = [
        {'username': 'admin',    'password': 'admin123',    'role': 'admin'},
        {'username': 'engineer', 'password': 'eng123',      'role': 'engineer'},
        {'username': 'viewer',   'password': 'view123',     'role': 'viewer'},
    ]