# 🛡 InfraGuard AI
### AI-Powered Digital Twin Platform for IT Infrastructure Failure Prediction

> Final Year MCA Project | AI/ML Specialization

---

## 📌 Project Overview

InfraGuard AI is a six-tier enterprise-grade infrastructure monitoring platform that implements a **Digital Twin** of IT infrastructure. It uses four complementary machine learning models to predict server failures before they occur, monitors 9 nodes in real time, generates automated PDF reports, and supports role-based access control with three user levels.

---

## 🏗 System Architecture

```
Tier 1 — Data Collection    → Real PC + 8 simulated servers (psutil)
Tier 2 — AI/ML Engine       → 4 models: IF, RF, LSTM, Autoencoder
Tier 3 — Alert Engine       → 4 severity levels, auto-resolve
Tier 4 — User Access        → Admin, Engineer, Viewer roles
Tier 5 — Dashboard          → 7-page live web interface
Tier 6 — Reporting Engine   → PDF + CSV export
```

---

## 🤖 AI Models

| Model | Type | Purpose |
|-------|------|---------|
| Isolation Forest | Unsupervised | Real-time anomaly detection (score 0–1) |
| Random Forest | Supervised Ensemble | Failure probability % + feature importance |
| LSTM Neural Network | Deep Learning | 30-minute metric forecasting + time to failure |
| Autoencoder | Neural Network | Deep pattern recognition + subtle anomaly detection |

All 4 models combine into a **weighted prediction engine** that produces a unified risk score per server.

---

## 🖥 Dashboard Pages

| Page | URL | Description |
|------|-----|-------------|
| Login | `/login` | Secure authentication with role-based access |
| Overview | `/overview` | System health, 9 server cards, live alerts |
| Digital Twin | `/twin` | Animated network topology map |
| Server Drilldown | `/servers` | Per-server charts and AI predictions |
| AI Models | `/ai` | Live comparison of all 4 models |
| Alert Center | `/alerts` | Manage alerts with ACK/Resolve |
| Reports | `/reports` | PDF/CSV/JSON export |

---

## ⚙ Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 + Flask |
| Database | SQLite |
| AI Models | scikit-learn + TensorFlow/Keras |
| Data Collection | psutil |
| Frontend | HTML5 + CSS3 + JavaScript |
| Charts | Chart.js |
| PDF Reports | ReportLab |
| Authentication | Flask Sessions |

---

## 📁 Project Structure

```
infraguard-ai/
├── app.py                  ← Main Flask server + all API endpoints
├── config.py               ← Central configuration
├── database.py             ← All database operations
├── collector.py            ← Data collection engine
├── alert_engine.py         ← Alert management
├── report_engine.py        ← PDF + CSV generation
├── simulate.py             ← Demo simulation tool
├── models/
│   ├── isolation_forest.py ← Model 1: Anomaly detection
│   ├── random_forest.py    ← Model 2: Failure classifier
│   ├── lstm_model.py       ← Model 3: Time series forecast
│   ├── autoencoder.py      ← Model 4: Pattern recognition
│   └── prediction_engine.py← Combines all 4 models
├── templates/
│   ├── login.html          ← Page 1: Login
│   ├── index.html          ← Page 2: Overview
│   ├── twin.html           ← Page 3: Digital Twin Map
│   ├── servers.html        ← Page 4: Server Drilldown
│   ├── ai_models.html      ← Page 5: AI Comparison
│   ├── alerts.html         ← Page 6: Alert Center
│   └── reports.html        ← Page 7: Reports
├── static/                 ← CSS and JS files
└── docs/                   ← Project report and presentation
```

---

## 🚀 Installation & Setup

### Prerequisites
- Python 3.11+
- Windows 10/11

### Step 1 — Clone or download the project
```
Place project folder at: C:\Users\<username>\infraguard-ai
```

### Step 2 — Install dependencies
```bash
pip install flask flask-login flask-sqlalchemy scikit-learn tensorflow numpy pandas psutil reportlab matplotlib
```

### Step 3 — Run the application
```bash
cd C:\Users\<username>\infraguard-ai
python app.py
```

### Step 4 — Open in browser
```
http://localhost:5000
```

---

## 👤 Default Login Credentials

| Username | Password | Role | Access Level |
|----------|----------|------|-------------|
| admin | admin123 | Admin | Full access + user management |
| engineer | eng123 | Engineer | Monitor + manage alerts |
| viewer | view123 | Viewer | Read-only dashboard |

---

## 📊 Servers Monitored

| Server ID | Name | Type |
|-----------|------|------|
| pc_local | Local PC | Physical (real metrics) |
| web_server_1 | Web Server 1 | Simulated |
| web_server_2 | Web Server 2 | Simulated |
| app_server | App Server | Simulated |
| db_mysql | MySQL Database | Simulated |
| db_redis | Redis Cache | Simulated |
| cloud_aws | AWS Instance | Simulated |
| cdn_server | CDN Server | Simulated |
| firewall | Firewall | Simulated |

---

## 🔔 Alert Thresholds

| Metric | Warning | High | Critical |
|--------|---------|------|----------|
| CPU | 70% | 85% | 95% |
| RAM | 70% | 85% | 95% |
| Disk | 75% | 88% | 95% |
| Temperature | 65°C | 75°C | 85°C |
| Error Rate | 2% | 5% | 10% |
| Response Time | 500ms | 1000ms | 2000ms |

---

## 🎯 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/login` | POST | Authenticate user |
| `/api/logout` | POST | Clear session |
| `/api/overview` | GET | Full system health |
| `/api/metrics/<id>` | GET | Server metric history |
| `/api/alerts` | GET | All alerts |
| `/api/alerts/<id>/acknowledge` | POST | Acknowledge alert |
| `/api/alerts/<id>/resolve` | POST | Resolve alert |
| `/api/predictions` | GET | AI predictions all servers |
| `/api/twin` | GET | Digital twin topology |
| `/api/simulate/failure` | POST | Inject fake failure |
| `/api/simulate/recover` | POST | Recover from failure |
| `/api/reports/pdf` | GET | Download PDF report |
| `/api/reports/csv` | GET | Download CSV export |

---

## 🎓 Viva Summary

*"InfraGuard AI is a six-tier enterprise monitoring platform that implements a Digital Twin of IT infrastructure. The AI engine uses four complementary machine learning models — Isolation Forest for unsupervised anomaly detection, Random Forest as an ensemble classifier for failure probability with explainable feature importance, LSTM for time-series forecasting, and an Autoencoder for deep pattern recognition. The system monitors 9 nodes in real time, generates automated PDF reports, and supports role-based access control with three user levels."*

---

## 📅 Development Timeline

| Week | Work Done |
|------|-----------|
| Week 1 | Foundation — config, database, collector, alert engine |
| Week 2 | AI Models — all 4 models + prediction engine |
| Week 3 | Backend — Flask server, APIs, login, reports, simulation |
| Week 4 | Dashboard — all 7 HTML pages with live charts |
| Week 5 | Testing, polish, README, demo prep |
| Week 6 | Project report, PPT, viva preparation |

---

*Developed as Final Year MCA Project — AI/ML Specialization*