# collector.py — Data Collection Engine for InfraGuard AI

import psutil
import random
import time
import threading
import math
from datetime import datetime
from database import save_metric, init_db, update_server_status
from config import Config


# ══════════════════════════════════════════════════════════════════════════════
#  REAL PC METRICS — reads actual data from your Windows machine
# ══════════════════════════════════════════════════════════════════════════════

def collect_real_pc():
    """Collect real metrics from the local PC using psutil."""
    try:
        # CPU — measure over 1 second for accuracy
        cpu = psutil.cpu_percent(interval=1)

        # RAM
        ram_info = psutil.virtual_memory()
        ram = ram_info.percent

        # Disk (C: drive on Windows)
        disk_info = psutil.disk_usage('C:\\')
        disk = disk_info.percent

        # Network
        net = psutil.net_io_counters()
        network_in  = round(net.bytes_recv / 1024 / 1024, 2)   # MB
        network_out = round(net.bytes_sent / 1024 / 1024, 2)   # MB

        # Temperature — not all Windows PCs support this
        temperature = None
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    if entries:
                        temperature = entries[0].current
                        break
        except Exception:
            pass
        if temperature is None:
            temperature = round(random.uniform(45, 65), 1)  # fallback

        # Processes
        processes = len(psutil.pids())

        # Response time — simulated for local PC
        response_time = round(random.uniform(5, 50), 2)

        # Error rate — simulated
        error_rate = round(random.uniform(0, 1), 3)

        return {
            'cpu':           round(cpu, 2),
            'ram':           round(ram, 2),
            'disk':          round(disk, 2),
            'network_in':    network_in,
            'network_out':   network_out,
            'temperature':   round(temperature, 1),
            'processes':     processes,
            'response_time': response_time,
            'error_rate':    error_rate,
        }
    except Exception as e:
        print(f"  [PC Collector Error] {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  SERVER SIMULATOR — generates realistic metrics for 8 fake servers
# ══════════════════════════════════════════════════════════════════════════════

class ServerSimulator:
    """
    Simulates a server with:
    - A unique personality (base load per server type)
    - Gradual drift (metrics slowly rise and fall over time)
    - Occasional stress events (sudden spikes)
    - Realistic noise
    """

    # Base profiles — what each server type normally looks like
    PROFILES = {
        'web': {
            'cpu':           (25, 55),
            'ram':           (40, 65),
            'disk':          (30, 50),
            'network_in':    (10, 80),
            'network_out':   (20, 100),
            'temperature':   (45, 65),
            'processes':     (80, 150),
            'response_time': (80, 300),
            'error_rate':    (0.1, 1.5),
        },
        'application': {
            'cpu':           (35, 70),
            'ram':           (55, 80),
            'disk':          (40, 65),
            'network_in':    (5, 40),
            'network_out':   (5, 40),
            'temperature':   (50, 70),
            'processes':     (120, 200),
            'response_time': (100, 400),
            'error_rate':    (0.2, 2.0),
        },
        'database': {
            'cpu':           (20, 60),
            'ram':           (60, 85),
            'disk':          (50, 80),
            'network_in':    (2, 20),
            'network_out':   (2, 20),
            'temperature':   (48, 68),
            'processes':     (50, 100),
            'response_time': (5, 50),
            'error_rate':    (0.0, 0.5),
        },
        'cache': {
            'cpu':           (10, 35),
            'ram':           (70, 90),
            'disk':          (20, 40),
            'network_in':    (5, 30),
            'network_out':   (5, 30),
            'temperature':   (40, 58),
            'processes':     (20, 50),
            'response_time': (1, 10),
            'error_rate':    (0.0, 0.3),
        },
        'cloud': {
            'cpu':           (20, 65),
            'ram':           (45, 75),
            'disk':          (35, 60),
            'network_in':    (20, 150),
            'network_out':   (20, 150),
            'temperature':   (42, 62),
            'processes':     (60, 130),
            'response_time': (50, 500),
            'error_rate':    (0.1, 1.0),
        },
        'cdn': {
            'cpu':           (15, 45),
            'ram':           (35, 60),
            'disk':          (40, 70),
            'network_in':    (50, 300),
            'network_out':   (50, 300),
            'temperature':   (40, 60),
            'processes':     (40, 80),
            'response_time': (20, 150),
            'error_rate':    (0.0, 0.8),
        },
        'network': {
            'cpu':           (10, 40),
            'ram':           (20, 45),
            'disk':          (10, 25),
            'network_in':    (100, 500),
            'network_out':   (100, 500),
            'temperature':   (38, 58),
            'processes':     (10, 30),
            'response_time': (1, 20),
            'error_rate':    (0.0, 0.2),
        },
    }

    def __init__(self, server_id, server_type):
        self.server_id   = server_id
        self.server_type = server_type
        self.profile     = self.PROFILES.get(server_type, self.PROFILES['web'])

        # Drift: each metric slowly wanders up or down
        self.drift       = {k: 0.0 for k in self.profile}
        self.drift_speed = {k: random.uniform(0.02, 0.08) for k in self.profile}

        # Stress event tracking
        self.stress_active    = False
        self.stress_remaining = 0
        self.stress_metric    = None
        self.tick             = 0   # counts how many readings taken


    def _maybe_trigger_stress(self):
        """Randomly start a stress event (like a traffic spike)."""
        if not self.stress_active and random.random() < 0.005:   # 0.5% chance per tick
            self.stress_active    = True
            self.stress_remaining = random.randint(20, 60)        # lasts 20–60 readings
            self.stress_metric    = random.choice(['cpu', 'ram', 'response_time', 'error_rate'])


    def _update_drift(self):
        """Slowly move metrics up and down to simulate real server behaviour."""
        for metric in self.drift:
            # Random walk — add a small step each tick
            step = random.uniform(-self.drift_speed[metric], self.drift_speed[metric])
            self.drift[metric] = max(-15, min(15, self.drift[metric] + step))


    def get_metrics(self):
        """Generate one realistic reading for this server."""
        self.tick += 1
        self._update_drift()
        self._maybe_trigger_stress()

        data = {}
        for metric, (low, high) in self.profile.items():
            # Base value — midpoint of range + drift
            mid   = (low + high) / 2
            span  = (high - low) / 2
            value = mid + self.drift[metric] + random.uniform(-span * 0.3, span * 0.3)

            # Apply stress boost if active
            if self.stress_active and metric == self.stress_metric:
                boost  = random.uniform(15, 35)
                value += boost
                self.stress_remaining -= 1
                if self.stress_remaining <= 0:
                    self.stress_active = False

            # Clamp to sensible bounds
            value = max(low * 0.5, min(high * 1.3, value))

            # Round appropriately
            if metric in ('processes',):
                data[metric] = int(value)
            else:
                data[metric] = round(value, 2)

        # Keep percentages in 0–100
        for pct_metric in ('cpu', 'ram', 'disk'):
            data[pct_metric] = max(0.0, min(99.9, data[pct_metric]))

        return data


# ══════════════════════════════════════════════════════════════════════════════
#  COLLECTION ENGINE — ties everything together
# ══════════════════════════════════════════════════════════════════════════════

class CollectionEngine:
    """
    Runs a background thread that:
    1. Collects real PC metrics
    2. Generates simulated metrics for all other servers
    3. Saves everything to the database
    4. Repeats every COLLECTION_INTERVAL seconds
    """

    def __init__(self):
        self.running    = False
        self.thread     = None
        self.simulators = {}
        self.latest     = {}
        self._setup_simulators()

    def _setup_simulators(self):
        """Create one simulator per non-physical server."""
        for server in Config.SERVERS:
            if server['type'] != 'physical':
                self.simulators[server['id']] = ServerSimulator(
                    server['id'], server['type']
                )

    def add_server(self, server_id, server_type):
        """Dynamically add a new server to the collection engine."""
        if server_id not in self.simulators:
            self.simulators[server_id] = ServerSimulator(server_id, server_type)
            print(f"  [Collector] New server added: {server_id} ({server_type})")
            return True
        return False

    def remove_server(self, server_id):
        """Dynamically remove a server from the collection engine."""
        if server_id in self.simulators:
            del self.simulators[server_id]
            if server_id in self.latest:
                del self.latest[server_id]
            print(f"  [Collector] Server removed: {server_id}")
            return True
        return False

    def get_all_server_ids(self):
        """Get all server IDs currently being collected."""
        ids = list(self.simulators.keys())
        for server in Config.SERVERS:
            if server['type'] == 'physical' and server['id'] not in ids:
                ids.append(server['id'])
        return ids

    def collect_all(self):
        """Collect one round of metrics from all servers including dynamic ones."""
        timestamp = datetime.now().strftime('%H:%M:%S')

        for server in Config.SERVERS:
            sid = server['id']

            if server['type'] == 'physical':
                data = collect_real_pc()
            else:
                if sid not in self.simulators:
                    self.simulators[sid] = ServerSimulator(sid, server['type'])
                data = self.simulators[sid].get_metrics()

            if data:
                save_metric(sid, data)
                self.latest[sid] = {**data, 'timestamp': timestamp, 'server_id': sid}
                cpu = data.get('cpu', 0)
                ram = data.get('ram', 0)
                if cpu > 90 or ram > 90:
                    update_server_status(sid, 'critical')
                elif cpu > 75 or ram > 75:
                    update_server_status(sid, 'warning')
                else:
                    update_server_status(sid, 'online')

        # Also collect from dynamically added servers
        from database import get_all_servers
        db_servers      = get_all_servers()
        config_ids      = [s['id'] for s in Config.SERVERS]
        dynamic_servers = [s for s in db_servers if s['id'] not in config_ids]

        for server in dynamic_servers:
            sid   = server['id']
            stype = server['type']
            if sid not in self.simulators:
                self.simulators[sid] = ServerSimulator(sid, stype)
            data = self.simulators[sid].get_metrics()
            if data:
                save_metric(sid, data)
                self.latest[sid] = {**data, 'timestamp': timestamp, 'server_id': sid}
                cpu = data.get('cpu', 0)
                ram = data.get('ram', 0)
                if cpu > 90 or ram > 90:
                    update_server_status(sid, 'critical')
                elif cpu > 75 or ram > 75:
                    update_server_status(sid, 'warning')
                else:
                    update_server_status(sid, 'online')


    def get_latest(self, server_id=None):
        """Return latest metrics — all servers or just one."""
        if server_id:
            return self.latest.get(server_id)
        return self.latest


    def _run_loop(self):
        """Background loop — collects data on a schedule."""
        print(f"  [Collector] Started — collecting every {Config.COLLECTION_INTERVAL}s")
        while self.running:
            try:
                self.collect_all()
            except Exception as e:
                print(f"  [Collector Error] {e}")
            time.sleep(Config.COLLECTION_INTERVAL)


    def start(self):
        """Start collecting data in the background."""
        if not self.running:
            self.running = True
            self.thread  = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            print("✅ Collection engine started in background.")


    def stop(self):
        """Stop the background collection."""
        self.running = False
        print("⛔ Collection engine stopped.")


# ══════════════════════════════════════════════════════════════════════════════
#  RUN DIRECTLY — Test the collector for 15 seconds
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("=== InfraGuard AI — Collector Test ===\n")
    init_db()

    engine = CollectionEngine()

    print("Collecting 3 rounds of data...\n")
    for round_num in range(1, 4):
        print(f"--- Round {round_num} ---")
        engine.collect_all()

        for server in Config.SERVERS:
            sid  = server['id']
            data = engine.get_latest(sid)
            if data:
                print(
                    f"  {sid:15} | "
                    f"CPU: {data['cpu']:5.1f}% | "
                    f"RAM: {data['ram']:5.1f}% | "
                    f"Disk: {data['disk']:5.1f}% | "
                    f"Temp: {data['temperature']:4.1f}°C"
                )
        print()
        time.sleep(2)

    print("✅ Collector test complete! Check your database — it should have 27 rows in metrics table.")