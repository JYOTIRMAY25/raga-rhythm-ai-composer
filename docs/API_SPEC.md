# RagaRhythm AI — REST API Specification (v1)

## Base URL
`/api/v1`

---

## 1. POST `/api/v1/analyze`

Uploads an audio file for Indian classical music feature extraction, raga detection, and rhythm analysis.

### Request
- **Content-Type**: `multipart/form-data`
- **Body**:
  - `file`: `UploadFile` (Required, Binary audio file in MP3, WAV, FLAC, OGG, or M4A format, max 25 MB).

### Processing Flow
1. Stream file chunks verifying total payload size does not exceed 25 MB.
2. Verify MIME type and audio magic bytes.
3. Generate UUID4 `analysis_id` and persist file to ephemeral scratch storage.
4. Enqueue DSP analysis task (Audio preprocessing → Tonic estimation → Pitch extraction → Swara analysis → Raga classification → Tala extraction).
5. Return initial job record with status `processing` or synchronous result.

### Response (202 Accepted / 200 OK)
```json
{
  "analysis_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "processing",
  "progress_percentage": 10,
  "current_stage": "preprocessing",
  "created_at": "2026-09-27T11:15:00Z"
}
```

### Error Responses
- `400 Bad Request`: `INVALID_AUDIO_FORMAT` — Unsupported MIME type or corrupted header.
- `413 Payload Too Large`: `FILE_SIZE_EXCEEDED` — Upload exceeds 25 MB limit.
- `422 Unprocessable Entity`: `EMPTY_FILE` — Zero-byte upload payload.

---

## 2. GET `/api/v1/analysis/{analysis_id}`

Retrieves the status, progress, and complete musical analysis result for a given recording.

### Request
- **Path Parameter**: `analysis_id` (UUID4 string)

### Response (200 OK — Completed)
```json
{
  "analysis_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "completed",
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
```

### Error Responses
- `404 Not Found`: `ANALYSIS_NOT_FOUND` — Specified analysis ID does not exist or has expired.
- `500 Internal Server Error`: `ANALYSIS_FAILED` — DSP extraction error with safe error message.

---

## 3. POST `/api/v1/generate`

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
