# Production Observability & Reliability

This document outlines the observability, correlation, health monitoring, metrics, and error handling architecture in RagaRhythm AI (Phase 5.3).

---

## 1. Overview & Principles

The observability subsystem in RagaRhythm AI provides comprehensive operational visibility while adhering to strict production and safety principles:
1. **Zero External Heavyweight Infrastructure**: Built entirely with Python standard library facilities (`logging`, `time.perf_counter`, `threading`, `contextvars`) without introducing external dependencies (no Prometheus client, Redis, Celery, or Datadog).
2. **Defensive Failure Isolation**: Observability operations are fail-safe. If logging or metrics collection encounters an internal error, the failure is caught and discarded to ensure request processing and DSP analysis pipelines are never compromised.
3. **Strict Privacy & Security**: Uploaded audio bytes, waveform arrays, authorization headers, API keys, credentials, and local filesystem paths are strictly excluded and redacted from logs and external responses.
4. **Predictable Low Overhead**: Monotonic stage timing and $O(1)$ statistical trackers maintain negligible CPU and memory footprints.

---

## 2. Structured Logging Architecture

### 2.1 Logger Configuration
The application configures a unified logger (`backend/app/observability/logging.py`) equipped with `StructuredLogFormatter`.
- Log records are emitted as structured JSON lines when configured for machine parsing or formatted key-value representations in development.
- Standard fields included in all structured records:
  - `timestamp`: UTC ISO-8601 formatted timestamp (`YYYY-MM-DDTHH:MM:SS.mmmmmmZ`)
  - `level`: Log severity (`INFO`, `WARNING`, `ERROR`, `CRITICAL`)
  - `logger`: Originating logger name (e.g., `ragarhythm.observability`, `ragarhythm.jobs`)
  - `event`: Stable semantic event name (see Section 2.2)
  - `request_id`: Active request correlation ID (or `None` if background/system task)
  - `job_id`: Associated analysis job identifier (when applicable)
  - `duration_ms`: Duration in milliseconds (float rounded to 2 decimal places for timed events)
  - `status`: Lifecycle status (`started`, `completed`, `failed`, `cancelled`, etc.)
  - `error_code`: Standardized error taxonomy code when an exception or failure occurs

### 2.2 Stable Event Names
Standardized event names ensure reliable aggregation, alerting, and log indexing:

| Event Name | Context | Description |
| :--- | :--- | :--- |
| `request.started` | HTTP Middleware | Emitted immediately upon receiving an inbound HTTP request. |
| `request.completed` | HTTP Middleware | Emitted upon successful completion of request with response status code and latency. |
| `request.failed` | HTTP Middleware | Emitted when an unhandled or handled HTTP error occurs. |
| `analysis.job.created` | Job Manager | Analysis job record allocated and assigned an ID. |
| `analysis.job.queued` | Job Manager | Analysis job task scheduled into the background thread pool executor. |
| `analysis.job.started` | Job Manager Worker | Worker thread picks up the job and begins pipeline execution. |
| `analysis.job.stage_started` | Analysis Pipeline | A discrete DSP pipeline stage commences. |
| `analysis.job.stage_completed` | Analysis Pipeline | A discrete DSP pipeline stage finishes successfully, recording elapsed time. |
| `analysis.job.completed` | Job Manager Worker | Entire analysis pipeline concludes, results persisted to job record. |
| `analysis.job.failed` | Job Manager Worker | Analysis job terminates with an error. |
| `analysis.job.cancelled` | Job Manager | Analysis job explicitly aborted via cancellation API. |

---

## 3. Request Correlation (`X-Request-ID`)

### 3.1 Traceability Flow
Every inbound HTTP request is tagged with an `X-Request-ID` correlation identifier:
1. **Client Header Inspection**: The `ObservabilityMiddleware` checks for an incoming `X-Request-ID` header.
2. **Sanitization & Validation**:
   - Client-provided IDs are sanitized against regex `^[A-Za-z0-9_-]{1,64}$`.
   - Any characters outside alphanumeric, hyphen, and underscore, or any control characters/newlines (`\r`, `\n`, `\x00`), are rejected.
   - Values exceeding 64 characters are rejected to prevent memory denial-of-service.
3. **Generation**: If the header is missing, empty, or invalid, a secure UUIDv4 identifier is generated automatically.
4. **Context Propagation**: Stored in a task-local `ContextVar` (`request_id_ctx`) so all downstream log calls within the async task automatically inherit the request ID without manual argument plumbing.
5. **Response Header**: The sanitized `X-Request-ID` is echoed in all HTTP responses and exception handlers.
6. **Frontend Integration**: The frontend API client extracts `X-Request-ID` from response headers and preserves it on error objects as `referenceId` for user support diagnostics.

---

## 4. Async Job Observability & Stage Timing

### 4.1 Job Lifecycle Tracking
Each `JobRecord` tracks high-resolution lifecycle metrics:
- `created_at`: Job creation timestamp.
- `started_at`: Timestamp when the background worker thread begins execution.
- `completed_at`: Terminal completion timestamp.
- `duration`: Total wall-clock runtime in seconds.
- `request_id`: Originating HTTP `X-Request-ID` captured at submission time.
- `stage_timings`: Mapping of pipeline stage names to their exact execution duration in seconds.

### 4.2 Pipeline Stage Timing
Every DSP stage is measured monotonically using `time.perf_counter()` via `StageTimer`:
- `INIT`
- `PREPROCESS`
- `TONIC`
- `PITCH`
- `TONIC_RESOLUTION`
- `SWARA`
- `RAGA`
- `RHYTHM_BEAT`
- `TALA`
- `FINAL`

Stage timings are recorded into `job.stage_timings` and tracked in aggregate within the in-process metrics registry.

---

## 5. Lightweight In-Process Metrics

### 5.1 Metrics Registry
The in-process `MetricsRegistry` (`backend/app/observability/metrics.py`) is thread-safe, bounded, and operates with zero external services.

#### Counters
- `requests_total`: Total HTTP requests processed (partitioned by method and status code).
- `requests_failed`: Total HTTP requests resulting in 4xx/5xx status codes.
- `analysis_jobs_created`: Number of analysis jobs initialized.
- `analysis_jobs_completed`: Analysis jobs successfully concluded.
- `analysis_jobs_failed`: Analysis jobs terminating in failure (partitioned by error code).
- `analysis_jobs_cancelled`: Jobs cancelled prior to completion.

#### Latency Tracking ($O(1)$ Online Statistics)
Latency metrics are managed via bounded `LatencyTracker` objects calculating:
- `count`: Total observations recorded.
- `total_ms`: Cumulative duration.
- `min_ms`: Minimum observed duration.
- `max_ms`: Maximum observed duration.
- `avg_ms`: Running arithmetic mean ($O(1)$ calculation without storing raw observations).
- Tracked for:
  - Overall HTTP request latency (`http_request_latency`)
  - Total analysis job execution duration (`analysis_job_duration`)
  - Individual stage execution times (`stage_duration.{stage_name}`)

#### Gauges
- `active_jobs`: Number of jobs currently being analyzed by worker threads.
- `queued_jobs`: Number of pending jobs awaiting worker capacity.
- Gauges are dynamically evaluated via registered callbacks to `JobManager` to prevent state drift.

### 5.2 Metrics Endpoint (`GET /api/v1/metrics`)
A diagnostics endpoint returns the current in-process snapshot:

```json
{
  "requests": {
    "total": 128,
    "failed": 2,
    "by_status": { "200": 115, "202": 11, "400": 2 },
    "latency": {
      "count": 128,
      "avg_ms": 14.25,
      "min_ms": 0.42,
      "max_ms": 112.50
    }
  },
  "jobs": {
    "created": 11,
    "completed": 10,
    "failed": 1,
    "cancelled": 0,
    "active": 0,
    "queued": 0,
    "duration": {
      "count": 10,
      "avg_ms": 1450.2,
      "min_ms": 980.1,
      "max_ms": 2100.5
    }
  },
  "stages": {
    "TONIC": { "count": 10, "avg_ms": 120.4, "min_ms": 95.0, "max_ms": 150.2 },
    "PITCH": { "count": 10, "avg_ms": 450.8, "min_ms": 410.2, "max_ms": 520.1 },
    "RAGA": { "count": 10, "avg_ms": 280.1, "min_ms": 250.0, "max_ms": 310.4 }
  }
}
```

---

## 6. Health & Readiness Probes

### 6.1 Process Health (`GET /api/v1/health`)
- **Purpose**: Fast liveness probe indicating whether the FastAPI process is alive and receiving HTTP traffic.
- **Status Codes**: Always returns `200 OK` with `{"status": "healthy"}`.
- **Performance**: Zero heavy computation; immediate return.

### 6.2 Application Readiness (`GET /api/v1/ready`)
- **Purpose**: Evaluates whether the application is fully initialized and capable of accepting analysis workloads.
- **Components Verified**:
  - Worker thread pool status (active, shutdown, or rejecting).
  - Job queue saturation (queue depth within configured limits).
  - Memory availability heuristics.
- **Status Codes**:
  - `200 OK`: `status: "ready"` or `status: "degraded"` (healthy, operating normally).
  - `503 Service Unavailable`: `status: "unavailable"` (application is shutting down or worker pool is exhausted).

---

## 7. Safe Error Taxonomy

API errors follow a safe, predictable contract and never leak internal execution details.

### 7.1 Standard Error Codes
- `INVALID_REQUEST`: Malformed parameters, payload invalid, or invalid client headers.
- `UNSUPPORTED_AUDIO`: Uploaded audio format cannot be decoded by librosa/soundfile.
- `FILE_TOO_LARGE`: Audio upload exceeds maximum permitted payload size.
- `QUEUE_FULL`: Worker queue is saturated; client should retry with backoff.
- `JOB_NOT_FOUND`: Referenced `job_id` does not exist or has expired.
- `JOB_CANCELLED`: Job was aborted by client request.
- `ANALYSIS_FAILED`: DSP analysis encountered an unexpected numerical or pipeline error.
- `SUBMISSION_FAILED`: Job submission was rejected by the executor.
- `INTERNAL_ERROR`: General server-side fault.

### 7.2 Security & Privacy Guarantees
- **No Stack Traces**: Stack traces are logged internally at `ERROR` level but are omitted from HTTP response payloads.
- **No Local Paths**: Absolute server paths (`C:\...`, `/home/...`) are sanitized from error messages.
- **No Secret Leakage**: Authorization headers, tokens, and raw binary audio chunks are never logged.

---

## 8. Operational Troubleshooting Guide

### 8.1 Correlating User Reports with Server Logs
1. Request the `Reference ID` (`X-Request-ID`) displayed in the client error toast.
2. Search server logs for the matching identifier:
   ```bash
   grep '"request_id": "req-xyz-123"' server.log
   ```
3. Locate the `request.failed` or `analysis.job.failed` event to view the sanitized error code and context.

### 8.2 Diagnosing Slow Analysis Jobs
1. Inspect the `stage_timings` returned in the job status response or aggregate stage latencies in `GET /api/v1/metrics`.
2. Determine which specific stage (`PITCH`, `TONIC`, `RAGA`, etc.) consumed excessive runtime.
3. Compare against baseline expectations (e.g., standard Yin-based pitch extraction vs. melodic phrase identification).

### 8.3 Handling Queue Saturation
1. Check `GET /api/v1/metrics` for `active_jobs` and `queued_jobs`.
2. Check `GET /api/v1/ready`. If the system responds with `503` or `degraded`, incoming analysis submissions will receive `QUEUE_FULL` (HTTP 429 / 503).
3. Ensure client applications observe exponential backoff.

---

## 9. Known Limitations & Reset Behavior

1. **Process-Local Scope**: Metrics are collected in memory and are local to the running Python process.
2. **Ephemeral Storage**: Metrics reset to zero when the server process is restarted or recycled.
3. **Multi-Worker Aggregation**: If deployed under multi-worker Uvicorn or Gunicorn with multiple processes, each process maintains its own independent metrics registry. A centralized scraper or metrics exporter would be required for cross-process aggregation in clustered multi-node environments.
