# Demo Walkthrough

This guide will help you demonstrate the Root Cause Analysis System to potential employers or stakeholders.

## Quick Start Demo (5 minutes)

### Prerequisites
- Docker and Docker Compose installed
- Python 3.11+ with `aiohttp` and `asyncpg` installed
- All services running

### Step-by-Step Demo

#### 1. Start the System
```bash
docker compose up -d
```

Wait for all services to be healthy (check with `docker compose ps`). This usually takes 30-60 seconds.

#### 2. Seed Demo Data
```bash
python scripts/seed_demo_data.py
```

This will:
- Generate 24 hours of metrics and logs data
- Create deployments, config changes, and feature flag changes
- Create a demo incident with anomalies
- Automatically trigger RCA analysis

**Expected output:**
- Metrics and logs data generated
- 3 deployments created
- 2 config changes created
- 2 feature flag changes created
- 1 incident created with 3 anomalies
- RCA analysis triggered

#### 3. Access the UI
Open your browser to: **http://localhost:3001**

You should see:
- **One incident** titled "Incident in user-service"
- Status: **OPEN**
- Start and end times

#### 4. View Incident Details
Click on the incident to see:
- **Anomalies**: 3 latency spike anomalies detected
- **Ranked Suspects**: Top suspects with evidence scores
  - The deployment that caused the incident should be ranked #1
  - Shows evidence like time proximity, metric deltas, etc.

#### 5. Demonstrate Labeling (Optional)
- Click "True Cause" or "Not Cause" on suspects
- This provides feedback to the ML model
- After enough labels, you can retrain the model

## Real-Time Demo (Live Detection)

This demo shows the system detecting incidents in real-time as they happen.

### Automated Real-Time Demo

Run the automated script:
```bash
python scripts/demo_live.py
```

**What happens:**
1. Script checks that all services are healthy
2. Injects 500ms latency into the mock service for 60 seconds
3. Waits for the detector to detect the anomaly and create an incident
4. Waits for RCA to generate suspects
5. Opens your browser to the incident page

**Timeline:**
- T+0s: Latency injected
- T+10s: First metrics with latency reported
- T+20-30s: Detector detects anomaly, creates incident
- T+30-40s: RCA worker generates suspects
- T+40s+: UI shows incident and suspects (updates every 3 seconds)

### Manual Real-Time Demo

1. **Start services:**
   ```bash
   docker compose up -d
   ```

2. **Open the UI:**
   - Navigate to http://localhost:3001
   - You should see a "Live" indicator in the top-right (green pulsing dot)
   - This indicates the UI is polling for updates every 3 seconds

3. **Inject latency:**
   ```bash
   python scripts/inject_latency.py --latency 500 --duration 60
   ```

4. **Watch the magic happen:**
   - Within 20-30 seconds, a new incident should appear in the UI
   - The incident will appear automatically (no refresh needed)
   - Click on the incident to see details
   - Suspects will appear within 30-40 seconds
   - Watch the suspect count update in real-time

5. **Try different latencies:**
   ```bash
   # Small latency spike (may not trigger)
   python scripts/inject_latency.py --latency 200 --duration 60
   
   # Large latency spike (will definitely trigger)
   python scripts/inject_latency.py --latency 1000 --duration 60
   
   # Reset to normal
   python scripts/inject_latency.py --reset
   ```

### Mock Service Endpoints

The mock service is available at http://localhost:8080:

- `GET /health` - Health check
- `GET /api/users` - Simulated API endpoint (with configurable latency)
- `POST /inject-latency?ms=500&duration=60` - Inject latency
- `POST /reset` - Reset to normal

### Real-Time UI Features

- **Live Indicator**: Green pulsing dot shows when polling is active
- **Auto-Refresh**: Incidents and suspects update every 3 seconds
- **No Page Reload**: Updates happen seamlessly in the background
- **New Item Highlighting**: New incidents and suspects appear automatically

## Full Feature Demo (10-15 minutes)

### 1. System Architecture Overview
Explain the microservices architecture:
- **API Service**: FastAPI backend for ingestion and queries
- **Detector Worker**: Real-time anomaly detection
- **RCA Worker**: Root cause analysis and suspect ranking
- **Frontend**: Next.js UI for visualization
- **ClickHouse**: Time-series data storage
- **Postgres**: Metadata and incidents storage
- **Kafka/Redpanda**: Event streaming

### 2. Data Flow Demonstration
1. **Ingestion**: Show how metrics/logs flow through the system
   - API receives data → ClickHouse storage → Kafka events
2. **Detection**: Detector worker processes metrics → detects anomalies
3. **Grouping**: Anomalies grouped into incidents
4. **RCA**: RCA worker generates and ranks suspects
5. **UI**: Frontend displays everything

### 3. Key Features to Highlight

#### Anomaly Detection
- Real-time detection using statistical methods
- Groups related anomalies into incidents
- Tracks multiple metrics per service

#### Root Cause Analysis
- **Candidate Generation**: Finds deployments, config changes, flags near incident time
- **Feature Extraction**: Analyzes:
  - Time proximity to incident
  - Metric correlation (blast radius)
  - Error log patterns
  - Code diff analysis
  - Historical risk
- **Ranking**: Heuristic scoring (can upgrade to ML with training data)

#### Machine Learning Integration
- System learns from human feedback (labels)
- Can train ML model after collecting labels
- Improves accuracy over time

### 4. API Exploration
Visit **http://localhost:8000/docs** to show:
- Interactive API documentation
- All available endpoints
- Request/response schemas

### 5. Monitoring (Optional)
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- Shows system metrics and health

## Troubleshooting Demo Issues

### No Incidents Showing
- Check if seed script completed successfully
- Verify API is running: `docker compose ps api`
- Check API health: `curl http://localhost:8000/health`

### No Suspects Showing
- RCA worker may need time to process (10-30 seconds)
- Check RCA worker logs: `docker compose logs rca`
- Manually trigger RCA: `python scripts/trigger_rca.py <incident_id>`

### Services Not Starting
- Check Docker resources (memory, CPU)
- Review logs: `docker compose logs`
- Ensure ports are not in use

## Demo Talking Points

1. **Production-Ready Architecture**
   - Microservices design for scalability
   - Event-driven for loose coupling
   - Proper separation of concerns

2. **Real-World Applicability**
   - Handles common incident scenarios
   - Integrates with existing monitoring tools
   - Provides actionable insights

3. **ML/AI Integration**
   - Learns from human feedback
   - Improves over time
   - Balances automation with human judgment

4. **Developer Experience**
   - Clean, maintainable code
   - Comprehensive API documentation
   - Easy to extend and customize

## Next Steps After Demo

1. **Collect Feedback**: Ask what features they'd like to see
2. **Show Code**: Walk through key components
3. **Discuss Extensions**: ML improvements, integrations, etc.
4. **Q&A**: Be ready to explain technical decisions

## Tips for a Great Demo

- **Practice first**: Run through the demo yourself
- **Have backup plan**: Know how to troubleshoot common issues
- **Keep it focused**: Don't get lost in technical details
- **Show value**: Emphasize how this solves real problems
- **Be honest**: Acknowledge limitations and future improvements

