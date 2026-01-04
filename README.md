# Production-Grade ML Regression RCA System

A production-grade root cause analysis system that automatically detects anomalies, groups incidents, and ranks suspects using machine learning. Built with modern microservices architecture and designed for real-world incident response scenarios.

## Features

- **Real-Time Anomaly Detection**: Statistical methods to detect metric anomalies across services
- **Intelligent Incident Grouping**: Automatically groups related anomalies into incidents
- **Root Cause Analysis**: Generates and ranks suspects (deployments, config changes, feature flags) based on:
  - Time proximity to incidents
  - Metric correlation and blast radius
  - Error log patterns
  - Code diff analysis
  - Historical risk factors
- **Machine Learning Integration**: Learns from human feedback to improve ranking accuracy
- **Modern Web UI**: Next.js frontend for viewing incidents, anomalies, and suspects
- **Production-Ready**: Docker-based deployment with monitoring (Prometheus/Grafana)
- **Event-Driven Architecture**: Kafka-compatible streaming for scalable processing
## Technology Stack

### Backend & Services
- **FastAPI** – Ingestion and query APIs
- **Detector Worker** – Anomaly detection and incident grouping
- **RCA Worker** – Root cause analysis, candidate generation, and suspect ranking
- **ClickHouse** – High-performance time-series metrics and logs storage
- **PostgreSQL** – Metadata, incidents, and suspects storage
- **Kafka / Redpanda** – Event streaming backbone (Kafka-compatible)
- **Redis** – Caching and rate limiting

### Frontend
- **Next.js 14** – React framework with App Router
- **TypeScript** – Type-safe frontend development
- **Modern CSS** – Clean, responsive UI for incident and suspect exploration

### ML / AI
- **scikit-learn** – Machine learning models
- **NumPy** – Numerical computing
- **Heuristic + ML Ranking** – Hybrid approach for RCA suspect prioritization


### Infrastructure
- **Docker & Docker Compose**: Containerization
- **Prometheus**: Metrics collection
- **Grafana**: Visualization and dashboards

## Screenshots

### Demo Dashboard
![Demo Dashboard](https://github.com/user-attachments/assets/6f1837c0-0bed-488c-a907-99fc7923c936)

### Incident Dashboard
![Incident Dashboard](https://github.com/user-attachments/assets/098d7c55-44da-43a9-91d0-8e9dbf84dd5e)

### Latency Dashboard
![Latency Dashboard](https://github.com/user-attachments/assets/10eb8d6f-73bf-48cb-9214-d50feebf44c2)

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- Node.js 18+ (for frontend development)

### Running the System

1. Start all services:
```bash
docker compose up -d
```

2. Wait for services to be healthy (check logs):
```bash
docker compose logs -f
```

3. Run smoke test:
```bash
python scripts/smoke_test.py
```

4. Run the live demo:
```bash
python scripts/demo_live.py
```

5. Access services:
- **Frontend UI**: http://localhost:3001/demo
- **Incident Dashboard**: http://localhost:3001
- **Grafana**: http://localhost:3000 (admin/admin)
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Prometheus**: http://localhost:9090

### Quick Demo

For a complete demo walkthrough, see [DEMO.md](DEMO.md).

**Quick demo (2 minutes):**
1. Start services: `docker compose up -d`
2. Run live demo: `python scripts/demo_live.py`
3. The script will automatically open the UI at http://localhost:3001
4. Click on the incident to see ranked suspects!

**Note:** The demo script automatically triggers RCA analysis, so suspects should appear within 10-30 seconds.

**Mock Service:**
The system includes a mock microservice (`mock-service`) that:
- Simulates a real service with configurable latency
- Reports metrics (p95_latency_ms, qps, error_rate) every 10 seconds
- Can be controlled via HTTP endpoints:
  - `POST /inject-latency?ms=500&duration=60` - Inject latency
  - `POST /reset` - Reset to normal
  - `GET /health` - Health check
- Accessible at http://localhost:8080

## Development

### Project Structure

```
.
├── apps/
│   ├── api/          # FastAPI application
│   ├── detector/     # Anomaly detection worker
│   └── rca/          # Root cause analysis worker
├── frontend/         # Next.js frontend
├── infra/            # Infrastructure configs
└── scripts/          # Utility scripts
```

## API Endpoints

### Ingestion
- `POST /ingest/metrics` - Ingest metrics (time-series data)
- `POST /ingest/logs` - Ingest log entries
- `POST /ingest/deployments` - Ingest deployment events
- `POST /ingest/config_changes` - Ingest configuration changes
- `POST /ingest/flag_changes` - Ingest feature flag changes

### Query
- `GET /incidents` - List incidents (supports `?status=OPEN` filter)
- `GET /incidents/{id}` - Get incident details
- `GET /incidents/{id}/anomalies` - Get anomalies for an incident
- `GET /incidents/{id}/suspects` - Get ranked suspects
- `POST /incidents/{id}/label` - Provide human feedback (true cause / not cause)
- `POST /incidents/{id}/rerun_rca` - Manually trigger RCA analysis

### Services
- `GET /services` - List all services
- `GET /services/metrics` - List metrics (supports `?service=<name>` filter)

### Health
- `GET /health` - System health check

## Troubleshooting

### Services Won't Start
- **Check Docker resources**: Ensure you have enough memory (recommended: 8GB+)
- **Check ports**: Make sure ports 8000, 3001, 5432, 9000, etc. are not in use
- **View logs**: `docker compose logs <service-name>` to see errors

### No Incidents Showing
- Verify demo script completed: Check for successful completion messages
- Check API health: `curl http://localhost:8000/health`
- Verify API is running: `docker compose ps api`

### No Suspects/Ranked Results
- RCA worker may need time: Wait 10-30 seconds after incident creation
- Check RCA worker logs: `docker compose logs rca`
- Manually trigger RCA: Use the API endpoint `/incidents/{id}/rerun_rca`
- Verify RCA worker is running: `docker compose ps rca`

### ClickHouse Connection Errors
- Check ClickHouse is healthy: `docker compose ps clickhouse`
- Verify authentication: Check `infra/clickhouse/users.xml` is mounted
- Restart ClickHouse: `docker compose restart clickhouse`

### Frontend Not Loading
- Check frontend is running: `docker compose ps frontend`
- Verify API URL: Check `NEXT_PUBLIC_API_URL` environment variable
- Check browser console: Look for CORS or connection errors

### Database Migration Issues
- If using async driver, use sync driver for migrations:
  ```bash
  docker compose exec -e DATABASE_URL="postgresql+psycopg2://rca:rca_password@postgres:5432/rca" api alembic upgrade head
  ```

## Performance Considerations

- **ClickHouse**: Optimized for time-series queries with partitioning and TTL
- **Postgres**: Indexed for fast incident and suspect queries
- **Kafka**: Handles high-throughput event streaming
- **Async Processing**: Workers process events asynchronously

## Security Notes

 **This is a demo system**. For production use:
- Add authentication/authorization
- Use secrets management for credentials
- Enable TLS/SSL
- Implement rate limiting
- Add input validation and sanitization
- Review and harden all configurations

## What Makes This Ready

### Production-Grade Architecture
- **Microservices Design**: Scalable, maintainable service separation
- **Event-Driven**: Loose coupling via Kafka/Redpanda event streaming
- **Async Processing**: Non-blocking I/O for high throughput
- **Containerized**: Docker-based deployment for consistency

### Technical Excellence
- **Type Safety**: TypeScript frontend, type hints in Python
- **Modern Stack**: FastAPI, Next.js, ClickHouse, PostgreSQL
- **ML Integration**: Heuristic + ML ranking with feedback loop
- **Monitoring**: Prometheus metrics and Grafana dashboards

### Developer Experience
- **Comprehensive Documentation**: README, DEMO guide, API docs
- **Easy Setup**: One-command demo scripts
- **Error Handling**: Graceful error handling throughout
- **Clean Code**: Well-structured, maintainable codebase

### Real-World Features
- **Anomaly Detection**: Statistical methods for real-time detection
- **Root Cause Analysis**: Multi-factor evidence scoring
- **Human Feedback Loop**: ML model learns from labels
- **Full-Stack UI**: Modern, responsive interface

### Demo-Ready
- **Complete Demo Flow**: End-to-end working system
- **Automated Setup**: Scripts handle all setup steps
- **Troubleshooting Guide**: Common issues documented
- **Live Demo**: Ready to showcase immediately

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

This is a portfolio project demonstrating:
- Microservices architecture
- Event-driven design
- ML/AI integration
- Modern full-stack development
- Production-ready practices

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


