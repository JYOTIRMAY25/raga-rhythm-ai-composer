# RagaRhythm AI — REST API Specification (v1)

## Base URL
`/api/v1`

---

## 1. POST `/api/v1/analyze`

Uploads an audio file for asynchronous Indian classical music feature extraction, raga detection, and rhythm analysis. Returns an unpredictable `job_id` with `QUEUED` or `PROCESSING` status immediately.

### Request
- **Content-Type**: `multipart/form-data`
- **Body**:
  - `file`: `UploadFile` (Required, Binary audio file in MP3, WAV, FLAC, OGG, or M4A format, max 25 MB).

### Processing Flow
1. Stream file chunks verifying total payload size does not exceed 25 MB.
2. Verify MIME type and audio magic bytes.
3. Generate unpredictable UUID4 `job_id` and persist file to isolated ephemeral temporary storage.
4. Enqueue DSP analysis task in bounded `ThreadPoolExecutor` worker pool.
5. Return initial job status response quickly without blocking for DSP completion.

### Response (202 Accepted)
```json
{
  "job_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "QUEUED",
  "progress": 0,
  "current_stage": "Queued",
  "created_at": "2026-10-06T11:15:00.000000+00:00",
  "started_at": null,
  "completed_at": null
}
```

### Error Responses
- `400 Bad Request`: `INVALID_AUDIO_FORMAT` — Unsupported MIME type or corrupted header.
- `413 Payload Too Large`: `FILE_SIZE_EXCEEDED` — Upload exceeds 25 MB limit.
- `422 Unprocessable Entity`: `EMPTY_FILE` — Zero-byte upload payload.
- `429 Too Many Requests`: `QUEUE_FULL` — Active job capacity reached.

---

## 2. GET `/api/v1/analysis/{job_id}`

Retrieves the current execution state, monotonic progress (0–100%), stage name, or final completed analysis result.

### Request
- **Path Parameter**: `job_id` (UUID4 string)

### Response (200 OK — In Progress)
```json
{
  "job_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "PROCESSING",
  "progress": 42,
  "current_stage": "Pitch extraction",
  "created_at": "2026-10-06T11:15:00.000000+00:00",
  "started_at": "2026-10-06T11:15:00.050000+00:00",
  "completed_at": null
}
```

### Response (200 OK — Completed)
```json
{
  "job_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "COMPLETED",
  "progress": 100,
  "current_stage": "Completed",
  "created_at": "2026-10-06T11:15:00.000000+00:00",
  "started_at": "2026-10-06T11:15:00.050000+00:00",
  "completed_at": "2026-10-06T11:15:08.200000+00:00",
  "result": {
  "audio_metadata": {
    "filename": "bhairavi_alaap.wav",
    "duration_seconds": 124.5,
    "sample_rate": 22050,
    "channels": 1,
    "format": "wav"
  },
  "tonic": {
    "frequency_hz": 146.83,
    "note_name": "D3",
    "confidence": 0.94
  },
  "raga": {
    "id": "bhairavi",
    "name": "Bhairavi",
    "thaat": "Bhairavi",
    "time": "Morning",
    "mood": "Devotional, Serene",
    "confidence": 0.89,
    "aroha": ["Sa", "r", "g", "m", "P", "d", "n", "S'"],
    "avaroha": ["S'", "n", "d", "P", "m", "g", "r", "Sa"],
    "vadi": "Ma",
    "samvadi": "Sa",
    "alternatives": [
      { "id": "bilawal", "name": "Bilawal", "confidence": 0.08 },
      { "id": "asavari", "name": "Asavari", "confidence": 0.03 }
    ]
  },
  "tala": {
    "id": "teental",
    "name": "Teental",
    "beats": 16,
    "matras": 16,
    "vibhag_structure": "4+4+4+4",
    "theka": "Dha Dhin Dhin Dha | Dha Dhin Dhin Dha | Dha Tin Tin Ta | Ta Dhin Dhin Dha",
    "confidence": 0.85
  },
  "tempo": {
    "bpm": 72.4,
    "category": "Vilambit"
  },
  "pitch_analysis": {
    "time_stamps": [0.0, 0.05, 0.10, 0.15],
    "frequencies_hz": [146.8, 147.2, 146.9, 155.4],
    "cents_from_tonic": [0.0, 4.7, 1.2, 98.6],
    "detected_swaras": ["Sa", "Komal Re", "Komal Ga", "Ma", "Pa", "Komal Dha", "Komal Ni"]
  },
  "rhythm_analysis": {
    "beat_positions_seconds": [0.83, 1.66, 2.49, 3.32],
    "onset_strengths": [0.12, 0.85, 0.34, 0.78]
  },
  "ai_explanation": "This performance exhibits prominent emphasis on Komal Re and Komal Ga, with microtonal glides (meend) typical of morning Raga Bhairavi in slow tempo."
  }
}
```

### Response (200 OK — Failed)
```json
{
  "job_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "FAILED",
  "progress": 35,
  "current_stage": "Pitch extraction",
  "created_at": "2026-10-06T11:15:00.000000+00:00",
  "started_at": "2026-10-06T11:15:00.050000+00:00",
  "completed_at": "2026-10-06T11:15:02.100000+00:00",
  "error": {
    "code": "ANALYSIS_FAILED",
    "message": "Audio signal too short or degraded for pitch extraction"
  }
}
```

### Response (200 OK — Cancelled)
```json
{
  "job_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "CANCELLED",
  "progress": 20,
  "current_stage": "Tonic estimation",
  "created_at": "2026-10-06T11:15:00.000000+00:00",
  "started_at": "2026-10-06T11:15:00.050000+00:00",
  "completed_at": "2026-10-06T11:15:01.500000+00:00"
}
```

### Error Responses
- `404 Not Found`: `JOB_NOT_FOUND` — Specified job ID does not exist, was cancelled, or has expired.

---

## 3. POST `/api/v1/analysis/{job_id}/cancel`

Requests cancellation of a queued or actively processing analysis job.

### Request
- **Path Parameter**: `job_id` (UUID4 string)

### Response (200 OK — Active or Queued Job Cancelled)
```json
{
  "job_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "CANCELLED",
  "message": "Job was cancelled before execution started."
}
```

### Response (200 OK — Idempotent Terminal State)
When cancellation is requested on an already terminal job (`COMPLETED`, `FAILED`, or previously `CANCELLED`), the endpoint returns 200 OK idempotently reflecting the terminal status:
```json
{
  "job_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "COMPLETED",
  "message": "Job has already reached terminal status: COMPLETED."
}
```

### Error Responses
- `404 Not Found`: `JOB_NOT_FOUND` — Specified job ID does not exist or has expired.

---

## 4. POST `/api/v1/generate`

Generates an algorithmic or AI-composed Indian classical music piece matching input theoretical parameters.

### Request
- **Content-Type**: `application/json`
- **Body (`GenerationRequest`)**:
```json
{
  "raga_id": "yaman",
  "tala_id": "teental",
  "style_id": "khayal",
  "tempo_bpm": 84,
  "duration_seconds": 60,
  "creativity_score": 50
}
```

### Validation Rules
- `raga_id`: Must match registered raga identifier.
- `tala_id`: Must match registered tala identifier.
- `tempo_bpm`: Integer or float between 40 and 240.
- `duration_seconds`: Integer between 15 and 300.
- `creativity_score`: Integer between 0 and 100.

### Response (200 OK — `GenerationResponse`)
```json
{
  "composition_id": "comp_1727419200",
  "raga": {
    "id": "yaman",
    "name": "Yaman"
  },
  "tala": {
    "id": "teental",
    "name": "Teental",
    "beats": 16
  },
  "style": {
    "id": "khayal",
    "name": "Khayal"
  },
  "tempo_bpm": 84,
  "duration_seconds": 60,
  "creativity_score": 50,
  "audio_url": "/api/v1/compositions/comp_1727419200.mp3",
  "generated_at": "2026-09-27T11:18:00Z"
}
```

---

## 4. GET `/api/v1/ragas` & GET `/api/v1/ragas/{raga_id}`

Retrieves the structured catalog of Indian classical ragas.

### Query Parameters for `/api/v1/ragas`
- `thaat`: Filter by Thaat (e.g., `Kalyan`, `Bhairav`, `Asavari`)
- `time`: Filter by time of day (e.g., `Morning`, `Evening`, `Night`)
- `search`: Case-insensitive text search over name and description.

### Response (200 OK — `RagaListResponse`)
```json
{
  "total": 8,
  "ragas": [
    {
      "id": "bhairavi",
      "name": "Bhairavi",
      "thaat": "Bhairavi",
      "time": "Morning",
      "mood": "Serene, Devotional",
      "aroha": ["Sa", "Komal Re", "Komal Ga", "Ma", "Pa", "Komal Dha", "Komal Ni", "Sa"],
      "avaroha": ["Sa", "Komal Ni", "Komal Dha", "Pa", "Ma", "Komal Ga", "Komal Re", "Sa"],
      "vadi": "Ma",
      "samvadi": "Sa",
      "description": "One of the most fundamental ragas in Hindustani classical music..."
    }
  ]
}
```

---

## 5. GET `/api/v1/talas` & GET `/api/v1/talas/{tala_id}`

Retrieves the rhythm and Tala patterns available in the system.

### Response (200 OK — `TalaListResponse`)
```json
{
  "total": 6,
  "talas": [
    {
      "id": "teental",
      "name": "Teental",
      "beats": 16,
      "vibhag": "4+4+4+4",
      "pattern": "Dha Dhin Dhin Dha | Dha Dhin Dhin Dha | Na Tin Tin Ta | Ta Dhin Dhin Dha",
      "description": "Most common 16-beat cycle in Hindustani music."
    }
  ]
}
```

---

## 6. GET `/api/v1/health`

Lightweight process liveness probe. Fast and non-invasive.

### Response (200 OK — `HealthResponse`)
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "api": "operational",
    "dsp_engine": "available",
    "dataset_adapter": "ready",
    "tala_engine": "available",
    "raga_engine": "available"
  },
  "timestamp": "2026-10-07T12:00:00.000000+00:00"
}
```

---

## 7. GET `/api/v1/ready`

Readiness probe indicating whether the instance can accept new analysis work. Inspects job worker threads, executor state, and queue capacity.

### Response (200 OK — Ready)
```json
{
  "status": "ready",
  "job_system": {
    "worker_capacity": 4,
    "queue_capacity": 50,
    "active_jobs": 2,
    "queue_available": 48
  },
  "timestamp": "2026-10-07T12:00:00.000000+00:00"
}
```

### Response (200 OK — Degraded when Queue Saturated)
When the queue is full (`queue_available == 0`), the probe returns `200 OK` with status `degraded`. The process is healthy and serves read queries, but new analysis submissions will receive `429 Too Many Requests`.

### Response (503 Service Unavailable — Not Ready)
Returned when the application is shutting down or the worker executor is unavailable.
```json
{
  "status": "shutting_down",
  "job_system": {
    "is_shutdown": true
  },
  "timestamp": "2026-10-07T12:00:00.000000+00:00"
}
```

---

## 8. GET `/api/v1/metrics`

Returns a bounded, thread-safe JSON snapshot of process-local runtime telemetry. Contains request counters, job lifecycle statistics, worker gauges, and stage durations.

### Response (200 OK)
```json
{
  "requests": {
    "total": 128,
    "failed": 2,
    "latency_ms": {
      "count": 128,
      "total_ms": 2560.4,
      "avg_ms": 20.0,
      "min_ms": 1.2,
      "max_ms": 145.8
    }
  },
  "jobs": {
    "created_total": 45,
    "completed_total": 42,
    "failed_total": 2,
    "cancelled_total": 1,
    "queued_current": 0,
    "processing_current": 0,
    "active_total": 0,
    "analysis_duration_ms": {
      "count": 42,
      "total_ms": 42000.0,
      "avg_ms": 1000.0,
      "min_ms": 450.0,
      "max_ms": 2100.0
    }
  },
  "workers": {
    "capacity": 4,
    "active": 0
  },
  "queue": {
    "capacity": 50,
    "available": 50
  },
  "stages": {
    "preprocessing": { "count": 42, "total_ms": 420.0, "avg_ms": 10.0, "min_ms": 3.0, "max_ms": 25.0 },
    "tonic_estimation": { "count": 42, "total_ms": 2100.0, "avg_ms": 50.0, "min_ms": 20.0, "max_ms": 120.0 }
  },
  "failures": {
    "INVALID_AUDIO_FORMAT": 2
  }
}
```

---

## 9. Observability Headers & Request Correlation

### `X-Request-ID`
Every API response returns the `X-Request-ID` header.
- If the client supplies `X-Request-ID`, it is validated and sanitized (alphanumeric, hyphen, underscore; max 64 characters).
- If absent, invalid, or malicious (newlines, control characters, oversized), the server generates a fresh UUID4.
- Correlated with asynchronous jobs: `POST /api/v1/analyze` records `request_id` in the `JobRecord` and lifecycle logs.

### `X-Response-Time-Ms`
Every API response returns elapsed wall-clock processing time in milliseconds.

---

## 10. Error Taxonomy

Standardized machine-readable error codes:
- `INVALID_REQUEST`: Malformed request payload or parameters.
- `INVALID_AUDIO_FORMAT`: Unsupported audio format or corrupted header magic bytes.
- `EMPTY_FILE`: Zero-byte uploaded audio payload.
- `FILE_SIZE_EXCEEDED`: Upload exceeds the 25 MB limit.
- `DURATION_EXCEEDED`: Audio duration exceeds the 10-minute (600s) maximum.
- `JOB_QUEUE_FULL`: Worker pool queue capacity reached (50 active jobs).
- `JOB_NOT_FOUND`: Specified job UUID does not exist or has expired.
- `JOB_CANCELLED`: Job was cooperatively cancelled.
- `SUBMISSION_FAILED`: Job could not be scheduled on the worker executor.
- `PROCESSING_ERROR`: DSP audio feature extraction failure (sanitized error message).
- `INTERNAL_SERVER_ERROR`: Unhandled internal server error.
