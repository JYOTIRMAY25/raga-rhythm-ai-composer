# Production Deployment & Operations Guide — RagaRhythm AI

This guide details the containerization, environment configuration, Cloud Run deployment architecture, operational monitoring, and security boundaries for RagaRhythm AI (Phase 5.4).

> **Important**: This guide documents deployment readiness and reproducible procedures. No production cloud deployment has taken place in this phase. Commands interacting with cloud infrastructure (`gcloud`, Google Cloud Run) require valid Google Cloud Platform (GCP) credentials and active projects.

---

## 1. Local Development Setup

### 1.1 Backend Service
```bash
# 1. Create and activate a Python 3.11 virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows PowerShell: .venv\Scripts\Activate.ps1

# 2. Install pinned dependencies
pip install -r backend/requirements.txt

# 3. Launch the development server
# Default dev configuration enables hot reload and local CORS origins
uvicorn backend.app.main:app --host 127.0.0.1 --port 8080 --reload
```

### 1.2 Frontend Client
```bash
# 1. Install Node dependencies (Node 20+ LTS recommended)
npm ci

# 2. Launch Vite development server
npm run dev
# The dev server binds to http://localhost:8080 or http://localhost:5173
```

---

## 2. Production Environment Variables Reference

| Variable | Environment | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `APP_ENV` | Backend | string | `development` | Target environment (`development`, `production`, `testing`, `staging`). In `production`, strict CORS and security rules are enforced. |
| `HOST` | Backend | string | `0.0.0.0` | Bind host IP address. |
| `PORT` | Backend | integer | `8080` | Network port for the ASGI server (automatically supplied by Cloud Run). Must be in `1..65535`. |
| `LOG_LEVEL` | Backend | string | `INFO` | Logging severity threshold (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). |
| `CORS_ORIGINS` | Backend | string | *(localhost list)* | Comma-separated list or JSON array of allowed origins. In `production`, wildcard `*` is strictly forbidden. |
| `MAX_UPLOAD_SIZE_MB` | Backend | float | `25.0` | Hard ceiling for audio ingestion uploads (1.0 to 500.0 MB). |
| `JOB_MAX_WORKERS` | Backend | integer | `4` | Concurrency limit for background DSP worker thread pool (1 to 64). |
| `JOB_QUEUE_CAPACITY` | Backend | integer | `50` | Maximum active queued + processing analysis jobs (1 to 10000). |
| `JOB_RETENTION_LIMIT` | Backend | integer | `1000` | Maximum completed/failed job records retained in memory (1 to 100000). |
| `JOB_RETENTION_TTL_SECONDS` | Backend | integer | `3600` | Retention TTL in seconds before eviction of terminal job records (60 to 2592000). |
| `GEMINI_API_KEY` | Backend | string | `None` | Optional Google Gemini API key for natural language musicological summaries. Graceful rule-based fallback active if omitted. |
| `GEMINI_MODEL` | Backend | string | `gemini-1.5-flash` | Gemini model endpoint to invoke. |
| `VITE_API_BASE_URL` | Frontend | string | `""` | Base URL for API requests. Baked at build time into static assets. Leave empty when frontend is served behind reverse proxy on same domain. |

---

## 3. Backend Container Build

The backend utilizes a multi-stage `Dockerfile` based on `python:3.11-slim`:
- **Builder Stage**: Installs C-extension build tooling and compiles dependencies into an isolated `/install` prefix.
- **Runtime Stage**: Copies dependencies, installs `libsndfile1` runtime library, creates a non-root `appuser:appgroup` (UID/GID 1001), and configures signal-aware `exec uvicorn`.

### Building the Image
```bash
docker build -t ragarhythm-backend:latest -f Dockerfile .
```

### Build Context Protection (`.dockerignore`)
The build context strictly excludes:
- Git metadata (`.git`, `.github`)
- Node and frontend artifacts (`node_modules`, `dist/`)
- Audio media and datasets (`*.wav`, `*.mp3`, `*.flac`, `*.ogg`, `saraga*`, `data/`)
- Python virtual environments and caches (`.venv/`, `__pycache__/`, `.pytest_cache/`)
- Local secrets (`.env`, `.env.*`)

---

## 4. Frontend Container Build

Frontend compilation uses `Dockerfile.frontend`:
- **Builder Stage**: Runs `npm ci` on `node:20-alpine` and compiles static assets via `npm run build`.
- **Runtime Stage**: Deploys static bundle onto lightweight `nginx:alpine` configured with SPA routing (`try_files $uri $uri/ /index.html`) and security headers.

```bash
docker build \
  --build-arg VITE_API_BASE_URL="https://api.yourdomain.com/api/v1" \
  -t ragarhythm-frontend:latest \
  -f Dockerfile.frontend .
```

*Note: Vite environment variables are evaluated at compile time. Do not pass runtime-only environment variables to already-built JavaScript bundles.*

---

## 5. Local Docker Execution

### Running Backend Container Locally
```bash
docker run -d \
  --name ragarhythm-backend \
  -p 8080:8080 \
  -e APP_ENV=production \
  -e PORT=8080 \
  -e CORS_ORIGINS="http://localhost:3000,http://localhost:5173" \
  -e LOG_LEVEL=INFO \
  ragarhythm-backend:latest
```

### Verifying Container Health
```bash
# Check liveness probe
curl -f http://localhost:8080/api/v1/health

# Check readiness probe
curl -f http://localhost:8080/api/v1/ready
```

---

## 6. Google Cloud Run Deployment (Stateless Container)

> **Prerequisite**: Requires Google Cloud SDK (`gcloud`), an active Google Cloud project with billing enabled, and permissions for Cloud Build, Artifact Registry, and Cloud Run.

### Step 1: Configure Project & Artifact Registry *(Requires GCP Credentials)*
```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"
export REPO_NAME="ragarhythm"

gcloud config set project ${PROJECT_ID}
gcloud artifacts repositories create ${REPO_NAME} \
  --repository-format=docker \
  --location=${REGION} \
  --description="RagaRhythm AI Docker Repository"
```

### Step 2: Build & Push via Google Cloud Build *(Requires GCP Credentials)*
```bash
gcloud builds submit \
  --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/backend:latest \
  -f Dockerfile .
```

### Step 3: Deploy to Cloud Run *(Requires GCP Credentials)*
```bash
gcloud run deploy ragarhythm-backend \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/backend:latest \
  --platform managed \
  --region ${REGION} \
  --allow-unauthenticated \
  --port 8080 \
  --memory 2Gi \
  --cpu 2 \
  --concurrency 40 \
  --min-instances 0 \
  --max-instances 10 \
  --set-env-vars="APP_ENV=production,LOG_LEVEL=INFO,CORS_ORIGINS=https://app.yourdomain.com,JOB_MAX_WORKERS=4,JOB_QUEUE_CAPACITY=50" \
  --set-secrets="GEMINI_API_KEY=ragarhythm-gemini-key:latest"
```

---

## 7. CORS Configuration & Security

1. **Development Behavior**: If `APP_ENV=development` (or unset), standard localhost origins (`http://localhost:8080`, `http://localhost:5173`, etc.) are permitted by default.
2. **Production Policy**:
   - `APP_ENV=production` enforces explicit domain whitelisting.
   - Wildcard `allow_origins=["*"]` is strictly rejected at application startup.
   - `CORS_ORIGINS` must be explicitly configured as comma-separated or JSON list of authorized frontend origins.
   - Example valid production configuration:
     `CORS_ORIGINS="https://ragarhythm.example.com,https://app.ragarhythm.example.com"`

---

## 8. Gemini API Integration & Graceful Degradation

- Google Gemini integration provides optional musicological explanations.
- Set `GEMINI_API_KEY` securely via environment variable or secret manager.
- If `GEMINI_API_KEY` is not provided or API quota is exhausted:
  - The application automatically falls back to deterministic rule-based musicological explanations.
  - Core DSP analysis (Tonic, Pitch, Swara, Raga, Tala) and algorithmic composition function completely uninterrupted.

---

## 9. Health & Readiness Verification

| Endpoint | Method | Expected Status | Purpose |
| :--- | :--- | :--- | :--- |
| `/api/v1/health` | `GET` | `200 OK` | Container liveness check. Returns `status: "healthy"` and subsystem statuses. Zero heavy computation. |
| `/api/v1/ready` | `GET` | `200 OK` / `503 Service Unavailable` | Subsystem readiness probe. Checks thread pool executor availability and queue capacity. Returns `status: "ready"` or `status: "degraded"`. Returns `503` during shutdown. |
| `/api/v1/metrics` | `GET` | `200 OK` | Process-local operational metrics snapshot (request counters, stage timings, job latencies). |

---

## 10. Resource Configuration & Safe Bounds

To prevent denial of service and memory exhaustion, the following upper bounds are enforced in code:
- **Maximum Upload Payload**: 25 MB (`MAX_UPLOAD_SIZE_MB`, streaming boundary check).
- **Maximum Audio Duration**: 600 seconds (10 minutes) maximum decoded audio.
- **Worker Concurrency**: 4 worker threads (`JOB_MAX_WORKERS`), isolated from the asyncio event loop.
- **Queue Depth**: 50 active jobs (`JOB_QUEUE_CAPACITY`). Returns HTTP 429 (`QUEUE_FULL`) on saturation.
- **Memory Retention Cap**: 1,000 completed job records (`JOB_RETENTION_LIMIT`) with opportunistic FIFO eviction.
- **Job Retention TTL**: 1 hour (`JOB_RETENTION_TTL_SECONDS`).

---

## 11. Temporary Filesystem Behavior & Ephemeral Storage

- **Storage Type**: The container filesystem is completely ephemeral.
- **Upload Isolation**: Inbound audio files are written to ephemeral temporary files named with UUID4 hashes (`app_temp_audio_*.tmp`).
- **Deterministic Cleanup**:
  - Unlinked immediately upon job completion in worker thread.
  - Unlinked in worker `finally` block on analysis failure.
  - Unlinked on explicit client job cancellation.
  - Unlinked on application shutdown.
- **Invariant**: The application does not rely on persistent local disk storage between container restarts.

---

## 12. Observability & Logging

- **Structured Output**: Emits structured JSON log lines containing `timestamp`, `level`, `event`, `request_id`, and `duration_ms`.
- **Request Tracing**: Inbound `X-Request-ID` headers are sanitized and traced across all logs and response headers.
- **Sensitive Data Redaction**: Audio waveforms, file paths, authorization headers, and API keys are strictly excluded from log records.

---

## 13. Rollback & Revision Management

In Google Cloud Run, rollback is instantaneous with zero downtime via revision traffic splitting:

```bash
# List previous revisions
gcloud run revisions list --service ragarhythm-backend --region us-central1

# Direct 100% of production traffic to previous stable revision (e.g. ragarhythm-backend-00004-abc)
gcloud run services update-traffic ragarhythm-backend \
  --region us-central1 \
  --to-revisions ragarhythm-backend-00004-abc=100
```

---

## 14. Pre-Deployment Security Checklist

- [ ] `.env` and `.env.*` are excluded from version control and Docker context.
- [ ] No hardcoded API keys or service account credentials in code or repository.
- [ ] `APP_ENV=production` is set in production container environment.
- [ ] Wildcard CORS (`*`) is absent; explicit HTTPS origins configured in `CORS_ORIGINS`.
- [ ] Container runs under unprivileged non-root user (`appuser`, UID 1001).
- [ ] Large datasets (`saraga1.5_hindustani/`) and audio files are excluded via `.dockerignore`.
- [ ] `MAX_UPLOAD_SIZE_MB` is bounded to prevent buffer overflow or DoS.
- [ ] Health and readiness probes are configured on the container orchestrator.

---

## 15. Known Operational Limitations

1. **In-Process Job State**: Analysis jobs and metrics are tracked in-process. If a container instance restarts or is scaled down by Cloud Run autoscaling, active in-flight jobs on that instance must be resubmitted by the client.
2. **Ephemeral Metrics**: In-process metrics reset to zero upon container restart. For cross-instance long-term metrics aggregation, deploy a Cloud Monitoring or OpenTelemetry sidecar.
3. **Audio Duration Ceiling**: Audio clips exceeding 10 minutes are rejected to bound peak memory usage during pitch tracking.
