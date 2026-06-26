# InfraGuard AI — Complete Viva Q&A Preparation
## FABINAS NAZAR | MCA Final Year | JAIN UNIVERSITY KOCHI

---

## HOW TO USE THIS DOCUMENT
- Read every question and answer at least 3 times
- Practice saying the answers out loud — not just reading them
- For technical questions, draw diagrams while explaining
- Always relate your answer back to InfraGuard AI specifically
- Never say "I don't know" — say "That is beyond the current scope but could be added in future work"

---

# SECTION 1 — PROJECT OVERVIEW QUESTIONS

**Q1: Introduce your project in 60 seconds.**
A: InfraGuard AI is a six-tier enterprise monitoring platform that implements a Digital Twin of IT infrastructure. The system monitors 9 servers in real time — one real PC and 8 simulated servers — collecting 8 metrics every 3 seconds. Four machine learning models run simultaneously: Isolation Forest for anomaly detection, Random Forest for failure probability, LSTM for 30-minute forecasting, and an Autoencoder for pattern recognition. These combine into a weighted prediction engine that gives a unified risk score per server. The results are displayed through a 7-page live dashboard built with Flask, with role-based access for Admin, Engineer and Viewer. The system also generates PDF health reports and CSV exports automatically.

---

**Q2: What is the main problem your project solves?**
A: Traditional monitoring tools like Nagios and Zabbix use static thresholds — they only alert after a metric has already crossed a limit, meaning the system is already failing when the alert fires. InfraGuard AI solves this by predicting failures before they occur. The LSTM model forecasts the next 30 minutes of metrics, and the combined AI engine can detect deteriorating patterns hours before a threshold is crossed. This shifts infrastructure management from reactive to proactive.

---

**Q3: What is a Digital Twin?**
A: A Digital Twin is a virtual replica of a physical system that maintains real-time synchronization with its physical counterpart. In InfraGuard AI, the Digital Twin Map on the twin page is a live visual representation of the entire network topology. Each server is shown as a node, connected by lines showing data flow direction. The nodes are colour coded by risk level and update in real time. This gives operators an instant visual understanding of infrastructure health that tables and charts cannot convey.

---

**Q4: Why did you choose this topic?**
A: Infrastructure failures cause significant financial losses — industry estimates put unplanned downtime at $5,600 per minute. Existing tools are purely reactive. By applying machine learning to infrastructure monitoring, we can predict failures and give operations teams time to act before users are affected. This combination of AI and DevOps is an emerging and highly relevant field, making it an ideal final year project that demonstrates both ML and software engineering skills.

---

**Q5: What is the novelty of your project?**
A: The key novelty is the combination of four distinct ML models in a weighted ensemble specifically designed for infrastructure monitoring. Most academic projects use a single model. Commercial tools like Dynatrace use ML but don't expose their models. InfraGuard AI uses four complementary models — each detecting different failure types — combines them through a weighted prediction engine, and presents results through an animated Digital Twin visualization. The entire system is built from scratch in Python and is fully explainable.

---

# SECTION 2 — ARCHITECTURE QUESTIONS

**Q6: Explain your six-tier architecture.**
A: Tier 1 is the Data Collection layer — psutil reads real PC metrics and a ServerSimulator generates realistic metrics for 8 simulated servers every 3 seconds. Tier 2 is the AI/ML Engine with four models running in parallel. Tier 3 is the Alert Engine which evaluates metrics against thresholds and manages the alert lifecycle. Tier 4 is the User Access layer handling authentication and role-based authorization. Tier 5 is the Dashboard — 7 HTML pages served by Flask. Tier 6 is the Reporting Engine generating PDF and CSV exports.

---

**Q7: Why did you use Flask instead of Django?**
A: Flask is a micro-framework — lightweight, flexible and requires no boilerplate. For InfraGuard AI, we needed a simple REST API server that integrates directly with Python ML libraries. Django is better suited for large applications with complex ORM requirements. Flask gave us full control over routing and API design without unnecessary overhead. For a project with 16 API endpoints and background threads, Flask's simplicity was the right choice.

---

**Q8: Why SQLite instead of MySQL or PostgreSQL?**
A: SQLite is file-based, requires zero configuration and setup, and is perfectly suitable for a single-machine monitoring application. It supports all the SQL operations we need and achieves over 50 reads and writes per second — more than sufficient for our 3-second collection interval. For a production deployment monitoring thousands of servers, PostgreSQL would be the better choice, and migration would be straightforward since we use standard SQL throughout.

---

**Q9: How do background threads work in your system?**
A: Python's threading module creates threads that run independently of the main Flask server. We have two background threads: the CollectionEngine thread that collects metrics every 3 seconds, and the prediction loop that runs AI models every 15 seconds. Both use daemon=True which means they automatically stop when the main program exits. The threads update an in-memory dictionary that the API endpoints read from, avoiding database queries for every dashboard refresh.

---

**Q10: What are the 6 database tables and why each one?**
A: Users stores login credentials with SHA-256 hashed passwords and roles. Servers stores the definitions of all 9 monitored nodes. Metrics stores every reading from every server — this is the largest table and the primary data source for AI training. Alerts stores the complete alert history with severity, value, threshold and resolution status. Predictions stores AI model outputs including combined scores, forecasts and model details. Model_accuracy tracks model performance over time for retraining decisions.

---

# SECTION 3 — AI/ML QUESTIONS

**Q11: Why did you use four models instead of one?**
A: Each model detects a different type of failure pattern. Isolation Forest catches sudden spikes — a server CPU jumping from 40% to 95% in seconds. Random Forest catches multi-metric patterns — CPU at 70% is fine, but CPU at 70% with RAM at 85% and error rate at 5% together suggests failure. LSTM catches gradual trends — a CPU slowly climbing 1% every minute for an hour. Autoencoder catches subtle baseline shifts — the overall pattern of a server changing in ways that don't trigger individual thresholds. Using all four together means no failure type is missed.

---

**Q12: Explain Isolation Forest in detail.**
A: Isolation Forest is an unsupervised anomaly detection algorithm. It works on the principle that anomalies are rare and different from normal observations. The algorithm builds an ensemble of isolation trees by randomly selecting a feature and a split value. Normal points, being clustered together, require many random cuts to isolate. Anomalous points, being different from the majority, are isolated in fewer cuts. The anomaly score is based on the average path length — shorter path equals more anomalous. In InfraGuard AI, we normalize this score to 0.0-1.0 and classify above 0.6 as anomaly, above 0.8 as severe anomaly.

---

**Q13: Explain Random Forest and feature importance.**
A: Random Forest builds 100 decision trees, each trained on a random subset of data and features. This randomness prevents overfitting. Each tree makes a prediction — failure risk or healthy — and the majority vote is the final answer. Feature importance measures how much each input metric contributed to the predictions across all 100 trees. In InfraGuard AI, this tells us which metric — CPU, RAM, disk etc. — is most responsible for a server's risk level. This is shown as horizontal bars on the Server Drilldown page. We use class_weight='balanced' because healthy readings vastly outnumber failure readings in the training data.

---

**Q14: Explain LSTM and why it is suitable for time series.**
A: LSTM stands for Long Short-Term Memory. It is a type of Recurrent Neural Network that maintains a cell state carrying information across time steps. This allows it to learn patterns that span multiple time points — like a CPU that has been climbing for the last 20 readings. Standard neural networks process each input independently and cannot learn these temporal patterns. In InfraGuard AI, the LSTM takes the last 20 readings as input and forecasts the next reading. We repeat this iteratively 10 times to forecast 30 minutes ahead. The architecture uses two LSTM layers with Dropout regularization to prevent overfitting.

---

**Q15: Explain the Autoencoder and reconstruction error.**
A: An Autoencoder has two parts: an encoder that compresses 8 input metrics to 4 values, and a decoder that reconstructs the original 8 from those 4. We train it only on normal data. The model learns to compress and reconstruct normal patterns accurately. When it receives anomalous data — unusual combinations of metric values — the reconstruction is poor because the model has never seen that pattern before. The reconstruction error, measured as mean squared error between input and output, serves as the anomaly score. The threshold is set at mean error plus two standard deviations from the training data.

---

**Q16: How do you combine the four models?**
A: The PredictionEngine class combines the four outputs using weighted averaging. Random Forest gets 35% weight because it is the most reliable for structured tabular data. Isolation Forest gets 25% as it excels at sudden spikes. LSTM and Autoencoder each get 20%. The LSTM contributes through an urgency function — imminent failure predictions score 0.95, no failure scores 0.05. The weighted sum gives a combined score from 0.0 to 1.0, which maps to LOW, MEDIUM, HIGH and CRITICAL risk levels. This ensemble approach is more robust than any single model.

---

**Q17: What is the contamination parameter in Isolation Forest?**
A: Contamination is the expected proportion of anomalies in the training data. We set it to 0.05, meaning we expect about 5% of readings to be anomalous. This affects the decision threshold — it determines what score is considered anomalous. Setting it too low makes the model miss real anomalies; too high causes false positives. 0.05 is a reasonable assumption for infrastructure data where most readings are normal.

---

**Q18: What is Dropout in neural networks?**
A: Dropout is a regularization technique that randomly disables a fraction of neurons during training. In InfraGuard AI's LSTM and Autoencoder, we use Dropout(0.2) meaning 20% of neurons are randomly disabled each training step. This forces the network to learn redundant representations rather than memorizing the training data. The result is better generalization to unseen data. Dropout is only active during training — during inference all neurons are active.

---

**Q19: Why do the models show low scores initially?**
A: The models require sufficient training data to establish a reliable normal baseline. With fewer than 50 readings, the Isolation Forest has not seen enough normal behavior to confidently classify anything as anomalous, so it is overly sensitive. The Random Forest shows 0% failure probability when all servers are healthy because it has not encountered failure examples in its limited training data. After accumulating 500+ readings, the models stabilize and produce accurate scores. This is normal ML behavior — all models improve with more data.

---

**Q20: What is MinMaxScaler and why use it?**
A: MinMaxScaler normalizes features to a 0-1 range. Neural networks like LSTM and Autoencoder are sensitive to feature scale — if CPU ranges from 0-100 and network traffic ranges from 0-5000, the network will focus disproportionately on the larger-valued feature. Normalization ensures all features contribute equally during training. We use MinMaxScaler for neural networks and StandardScaler (zero mean, unit variance) for tree-based models.

---

# SECTION 4 — DASHBOARD QUESTIONS

**Q21: How does the dashboard update in real time without reloading?**
A: Each page uses JavaScript's setInterval function to call Flask API endpoints every 3 seconds. The fetch API sends an HTTP GET request, receives JSON data, and JavaScript directly updates the DOM elements — changing text content, bar widths, chart data and element colors — without triggering a page reload. This is called AJAX (Asynchronous JavaScript and XML). Chart.js updates use chart.update('none') to skip animation, preventing flickering during rapid updates.

---

**Q22: Explain the Digital Twin Map implementation.**
A: The Digital Twin Map is drawn entirely using the HTML5 Canvas 2D API. Each server has predefined position coordinates as percentages of canvas size, so it adapts to different screen sizes. The draw loop runs at 60 frames per second using requestAnimationFrame. Each frame: clears the canvas, draws the grid, draws connection lines with animated dots showing data flow direction, draws server nodes as circles with glow effects, and adds text labels. Click detection converts mouse coordinates to canvas coordinates and checks proximity to each node center. Critical servers pulse with an animated ring using a sine wave function.

---

**Q23: How does login and session management work?**
A: When a user submits the login form, JavaScript sends a POST request to /api/login with username and password as JSON. Flask's verify_user function hashes the password with SHA-256 and compares it to the stored hash. On success, Flask stores the user's id, username and role in the session — an encrypted cookie stored in the browser. Every subsequent request automatically includes this cookie. The login_required decorator on every protected route checks for the session cookie; if absent, it redirects to login. Logout clears the session completely.

---

**Q24: What is role-based access control and how is it implemented?**
A: RBAC restricts system access based on user roles. InfraGuard AI has three roles: Admin has full access including user management and simulation; Engineer can monitor and manage alerts but not manage users; Viewer has read-only access. Implementation uses session data — the user's role is stored in the session cookie on login. Protected endpoints check the role before processing: the simulation endpoint returns 403 Forbidden if the role is not admin or engineer, and the user management endpoint returns 403 if not admin.

---

**Q25: How does Chart.js work in your project?**
A: Chart.js is a JavaScript library that renders charts on HTML5 canvas elements. We load it from a CDN. For each chart, we define a type (line, bar, radar), a data object with labels and dataset values, and an options object for styling. To update a chart with new data, we directly modify chart.data.labels and chart.data.datasets[0].data arrays and call chart.update('none'). The 'none' parameter disables animation during live updates to prevent visual jitter.

---

# SECTION 5 — ALERT SYSTEM QUESTIONS

**Q26: Explain the alert deduplication system.**
A: Before creating a new alert, the alert engine queries the database for existing active alerts with the same server_id and metric combination. If found, the new alert is suppressed. This prevents alert storms — without deduplication, a server with high CPU would generate a new CRITICAL alert every 3 seconds, creating hundreds of identical alerts that overwhelm the operations team. With deduplication, only one alert exists per metric per server at any time, regardless of how many times the threshold is crossed.

---

**Q27: What is alert auto-resolution?**
A: Auto-resolution automatically closes active alerts when the corresponding metric returns to normal. After each metric collection, the alert engine checks if the current value is below all thresholds. If so, auto_resolve_alerts() is called, which sets the alert status to 'resolved' and records the resolution timestamp. This means the alert timeline accurately reflects when the issue started and when it ended, without requiring manual intervention from the operations team.

---

**Q28: What are the four severity levels?**
A: INFO is for informational events that don't require action. WARNING means a metric has crossed the warning threshold and should be monitored — for example CPU above 70%. HIGH means the metric is significantly elevated and needs attention soon — for example CPU above 85%. CRITICAL means immediate action required — for example CPU above 95%. The thresholds are configurable in config.py for each metric.

---

# SECTION 6 — TECHNICAL IMPLEMENTATION QUESTIONS

**Q29: How does psutil collect real PC metrics?**
A: psutil is a Python library that provides a cross-platform interface to system information. cpu_percent(interval=1) measures CPU usage over a 1-second interval for accuracy. virtual_memory() returns RAM statistics. disk_usage('C:\\') returns disk statistics for the C drive. net_io_counters() returns cumulative bytes sent and received since boot. sensors_temperatures() attempts to read hardware temperature sensors — if unavailable on Windows, we fall back to a simulated value. len(psutil.pids()) counts running processes.

---

**Q30: How does the server simulation work?**
A: The ServerSimulator class gives each server a personality — predefined CPU, RAM, disk and other metric ranges based on server type. For example, Redis cache servers have high RAM (70-90%) and very fast response time (1-10ms). A drift mechanism implements a random walk — each tick adds a small random increment to an offset value, which slowly moves metrics up and down within bounds. A stress event mechanism has a 0.5% chance per tick of triggering a spike on a random metric, lasting 20-60 readings, simulating traffic spikes and scheduled jobs.

---

**Q31: What is ReportLab and how do you use it?**
A: ReportLab is a Python library for programmatic PDF generation. Instead of designing a PDF visually, we build it in code using elements called Flowables — Paragraphs, Tables, Spacers and HRFlowables. These are collected in a list called the story and passed to SimpleDocTemplate which handles page layout and pagination. TableStyle applies formatting to tables — background colors, text colors, fonts and borders. The PDF is written to a BytesIO buffer in memory and returned as a file download response, never saved to disk.

---

**Q32: What is the sys.path fix in the models folder?**
A: Python resolves imports relative to the current working directory. When model files in the models/ subdirectory try to import from database.py or config.py in the parent folder, Python cannot find them by default. The sys.path.insert(0, parent_directory) line adds the parent folder to Python's module search path, allowing the import to succeed. This is necessary because we run all files from the infraguard-ai root directory.

---

**Q33: How does PDF download work in the browser?**
A: The JavaScript fetch API calls /api/reports/pdf. Flask generates the PDF in memory as bytes, wraps it in a BytesIO buffer and returns it using send_file with mimetype 'application/pdf' and as_attachment=True. JavaScript receives the response as a Blob, creates a temporary object URL using URL.createObjectURL(), creates an invisible anchor element, sets its href to the URL and its download attribute to the filename, programmatically clicks it to trigger the download, then revokes the URL to free memory.

---

# SECTION 7 — EXPECTED DIFFICULT QUESTIONS

**Q34: How accurate are your AI models?**
A: The models are not evaluated against labeled ground truth data since we don't have real failure events to validate against. Instead, we validate behavior: Isolation Forest correctly assigns low scores (0.1-0.3) to normal readings and high scores (0.7-0.95) to injected failure readings. Random Forest correctly predicts near-0% failure probability for healthy servers and 85-99% when extreme metrics are injected. LSTM correctly forecasts stable values for stable metrics and rising trends for rising metrics. This behavioral validation demonstrates the models work as intended.

---

**Q35: How is your project different from Prometheus + Grafana?**
A: Prometheus and Grafana are excellent tools for metrics collection and visualization, but they do not include built-in machine learning for failure prediction. They use static alerting rules. InfraGuard AI adds four ML models that learn from historical data and predict failures before thresholds are crossed. The Digital Twin visualization is also unique — Grafana shows time-series charts, not an animated network topology. InfraGuard AI is designed as an academic demonstration of ML applied to infrastructure monitoring.

---

**Q36: Can this system scale to monitor hundreds of servers?**
A: The current SQLite database would need to be replaced with PostgreSQL for horizontal scaling. The ML models would need to move to a distributed training framework. The collector would need to be distributed across multiple collection agents. However, the six-tier architecture is designed to support this — each tier can be scaled independently. The API layer is stateless and could be load-balanced. This scalability path is described in the Future Work section of the report.

---

**Q37: What security measures does your system have?**
A: Passwords are hashed with SHA-256 — plain text passwords are never stored. Session cookies use Flask's secret key for encryption. All API endpoints require authentication via the login_required decorator. Role-based access control prevents unauthorized actions — viewers cannot simulate failures and engineers cannot manage users. In a production system, we would add HTTPS, rate limiting, CSRF protection and JWT tokens.

---

**Q38: What happens if the AI models make a wrong prediction?**
A: False positives — predicting failure when the server is healthy — are handled by the weighted ensemble approach. Since all four models must collectively score high for the combined score to reach CRITICAL, a single model's false positive is dampened by the other three models' normal scores. False negatives — missing a real failure — are mitigated by the threshold-based alert system which runs in parallel with the AI models. Even if AI models miss an anomaly, the traditional threshold alerts will catch explicit threshold violations.

---

**Q39: Why is your disk usage always showing 93%?**
A: That is the real disk usage of my Windows PC collected by psutil. The disk metric is reading the actual C: drive of my machine. This is a genuine real-world reading, not simulated, which demonstrates that Tier 1 of the architecture successfully collects real hardware metrics. The system correctly generated a HIGH alert for this disk usage since it exceeds the 88% HIGH threshold defined in config.py.

---

**Q40: What would you improve if you had more time?**
A: The highest priority improvement would be adding email and SMS notifications for critical alerts, making the system useful in production. Second, I would add SSH and SNMP support for monitoring real remote servers rather than simulations. Third, I would implement model accuracy tracking — comparing AI predictions against actual outcomes over time — to enable automatic retraining when accuracy degrades. Fourth, a mobile-responsive dashboard design would make monitoring accessible from smartphones. These are all noted in the Future Work section.

---

# SECTION 8 — QUICK FIRE ANSWERS

| Question | Answer |
|----------|--------|
| What language is the backend written in? | Python 3.11 |
| What web framework did you use? | Flask |
| What database? | SQLite |
| How many servers are monitored? | 9 (1 real + 8 simulated) |
| How many metrics per server? | 8 |
| How often is data collected? | Every 3 seconds |
| How often do AI predictions run? | Every 15 seconds |
| How many AI models? | 4 |
| Which model gets highest weight? | Random Forest (35%) |
| How many dashboard pages? | 7 |
| How many API endpoints? | 16 |
| How many user roles? | 3 (Admin/Engineer/Viewer) |
| How many database tables? | 6 |
| What library for PDF? | ReportLab |
| What library for charts? | Chart.js |
| What library for real PC metrics? | psutil |
| What is the Digital Twin Map drawn with? | HTML5 Canvas 2D API |
| How are passwords stored? | SHA-256 hash |
| What is alert deduplication? | Skip duplicate active alerts for same server+metric |
| What is auto-resolution? | Automatically close alert when metric returns to normal |

---

# SECTION 9 — VIVA DAY CHECKLIST

**The night before viva:**
- [ ] Run python app.py and confirm it starts cleanly
- [ ] Open all 7 pages and confirm they load
- [ ] Test simulate failure on alerts page
- [ ] Download a PDF report and confirm it opens
- [ ] Practice the 60-second project introduction out loud
- [ ] Review all Quick Fire Answers
- [ ] Get good sleep

**Day of viva:**
- [ ] Start app.py before the examiner arrives
- [ ] Have the browser open at http://localhost:5000/login
- [ ] Have the PDF report ready to show
- [ ] Have the PPT ready to present
- [ ] Stay calm — you built every line of this system yourself

---

*InfraGuard AI — Built by FABINAS NAZAR | JAIN UNIVERSITY KOCHI | March 2026*