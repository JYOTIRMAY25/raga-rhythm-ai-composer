# Production Deployment Guide — RagaRhythm AI

Comprehensive guide for local development, containerization, and Cloud Run production deployment of RagaRhythm AI.

---

## 1. Architecture Overview

- **Backend**: FastAPI (Python 3.11) with deterministic algorithmic composition, microtonal Shruti intonation, multi-timbral synthesis, and RIFF 16-bit PCM WAV rendering.
- **Frontend**: React 18 with TypeScript, Vite, Tailwind CSS, Radix UI, and Web Audio API integration.
- **Observability**: Structured JSON logging, `X-Request-ID` tracing, and lightweight `/api/v1/health` probes.
- **Caching**: Thread-safe bounded LRU memory caching for symbolic compositions and audio WAV streams with explicit `AUDIO_RENDERER_VERSION = "1.0"` invalidation.

---

## 2. Environment Variables

| Variable | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `PORT` | No | `8080` | Port for the backend server |
| `HOST` | No | `0.0.0.0` | Bind address for backend server |
| `GEMINI_API_KEY` | Optional | `None` | Google Gemini API key for natural language explanations (graceful fallback active if omitted) |
| `CORS_ORIGINS` | No | `*` | Allowed CORS origins list |
| `VITE_API_BASE_URL` | No | `http://localhost:8080` | Frontend backend API URL |

---

## 3. Local Development

### Backend Startup
```bash
# 1. Create and activate Python virtual environment
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r backend/requirements.txt

# 3. Launch local dev server
uvicorn backend.app.main:app --host 127.0.0.1 --port 8080 --reload
```

### Frontend Startup
```bash
# 1. Install Node dependencies
npm install

# 2. Start Vite dev server
npm run dev
```

---

## 4. Docker Container Build & Run

### Building Backend Image
```bash
docker build -t ragarhythm-backend:latest -f Dockerfile .
```

### Running Backend Container
```bash
docker run -d \
  --name ragarhythm-api \
  -p 8080:8080 \
  -e PORT=8080 \
  -e GEMINI_API_KEY="your-api-key-here" \
  ragarhythm-backend:latest
```

### Verifying Container Health
```bash
curl -f http://localhost:8080/api/v1/health
```

---

## 5. Google Cloud Run Deployment

The backend container is 100% stateless and ready for serverless deployment on Google Cloud Run:

```bash
# 1. Build and submit image to Google Artifact Registry
gcloud builds submit --tag gcr.io/[PROJECT_ID]/ragarhythm-backend:latest

# 2. Deploy to Cloud Run
gcloud run deploy ragarhythm-backend \
  --image gcr.io/[PROJECT_ID]/ragarhythm-backend:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --set-env-vars="PORT=8080"
```

---

## 6. Health Checks & Monitoring

- **Readiness Probe**: `GET /api/v1/health` (Lightweight probe returning `{"status":"ok","version":"1.0.0"}`)
- **Cache Metrics**: `GET /api/v1/generate/cache/stats` (Returns entries, memory usage, hit ratio)
- **Cache Clear**: `POST /api/v1/generate/cache/clear` (Flushes in-memory caches)

---

## 7. Troubleshooting & Rollback

1. **Slow Audio Synthesis**:
   - Check duration parameter. Maximum duration is bounded at 300 seconds (5 minutes).
   - Ensure `AUDIO_RENDERER_VERSION` matches current release.
2. **Missing Gemini Explanations**:
   - The system automatically provides high-quality heuristic musicological rule fallbacks if `GEMINI_API_KEY` is not provided or quota is exceeded.
3. **Rollback**:
   - Revert to previous Docker image tag via Cloud Run revision traffic splitting:
     `gcloud run services update-traffic ragarhythm-backend --to-revisions=[PREVIOUS_REVISION]=100`
