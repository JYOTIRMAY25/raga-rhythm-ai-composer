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

### Response (200 OK)
```json
{
  "job_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "CANCELLED",
  "message": "Job successfully cancelled"
}
```

### Error Responses
- `404 Not Found`: `JOB_NOT_FOUND` — Specified job ID does not exist or has expired.
- `400 Bad Request`: `INVALID_STATE` — Job has already reached a terminal state (`COMPLETED` or `FAILED`).

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

System health check and engine readiness probe.

### Response (200 OK)
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "api": "operational",
    "dsp_engine": "available",
    "gemini_ai": "available",
    "dataset_adapter": "ready"
  },
  "timestamp": "2026-09-27T11:18:40Z"
}
```
