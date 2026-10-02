# RagaRhythm AI — System Architecture & Backend Design

## 1. High-Level Architecture Overview

RagaRhythm AI operates on a decoupled client-server architecture:
- **Frontend Client**: React 18 + TypeScript + Vite + Tailwind CSS SPA, providing an interactive Indian classical music dashboard, audio uploader, waveform player, and composition controls.
- **Backend API Server**: Python FastAPI application delivering high-performance asynchronous REST endpoints for audio ingestion, feature extraction, heuristic/ML classification, and AI explanation orchestration.
- **Audio Processing & Music Theory Engine**: Modular DSP pipeline utilizing `librosa`, `numpy`, and `scipy` for pitch contour extraction, tonic (*Sa*) estimation, swara mapping, and rhythm/tala cycle analysis.
- **AI Explanation & Synthesis Layer**: Server-side integration with Gemini API for grounded musicological explanations and algorithmic music generation.

```text
┌────────────────────────────────────────────────────────────────────────┐
│                          Frontend (React SPA)                          │
│  [AudioUploader]    [AnalysisResult]   [CompositionGenerator/Player]   │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │ HTTP / JSON & Multipart
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        FastAPI Application Gateway                     │
│  - CORS & Security Middleware          - Request Validation (Pydantic)  │
│  - Rate Limiting & File Bounds         - Exception Handlers             │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │
         ┌────────────────────────┴────────────────────────┐
         ▼                                                 ▼
┌────────────────────────────────┐               ┌───────────────────────┐
│     Audio Processing Engine    │               │  Domain Services      │
│  - AudioPreprocessor           │               │  - RagaService        │
│  - TonicEstimator (Sa F0)      │               │  - TalaService        │
│  - PitchExtractor (pYIN/CREPE) │               │  - GenerationService  │
│  - SwaraAnalyzer (Cents/Notes) │               │  - GeminiAIService    │
│  - TalaDetector (Beats/Matras) │               │  - DatasetAdapter     │
│  - RagaDetector (PCD/Phrases)  │               └───────────────────────┘
└────────────────────────────────┘
```

---

## 2. Backend Folder Structure

```text
backend/
├── app/
│   ├── main.py                    # FastAPI entrypoint, lifespan, CORS, route registration
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                # Dependency injection (rate limits, service singletons)
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py          # Unified v1 API router
│   │       ├── endpoints/
│   │       │   ├── analyze.py     # POST /api/v1/analyze, GET /api/v1/analysis/{id}
│   │       │   ├── generate.py    # POST /api/v1/generate
│   │       │   ├── ragas.py       # GET /api/v1/ragas, GET /api/v1/ragas/{id}
│   │       │   ├── talas.py       # GET /api/v1/talas, GET /api/v1/talas/{id}
│   │       │   └── health.py      # GET /api/v1/health
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py              # Pydantic Settings, environment variables, security constants
│   │   ├── security.py            # Upload verification, MIME sniffing, sanitization
│   │   └── exceptions.py          # Custom domain exceptions and HTTP error mappings
│   ├── models/
│   │   ├── __init__.py
│   │   ├── domain.py              # Core entities (Raga, Tala, Swara, PerformanceStyle)
│   │   └── analysis.py            # AnalysisRecord, AudioMetadata, PitchContour
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── analysis.py            # AnalysisRequest, AnalysisResponse, StatusResponse
│   │   ├── generation.py          # GenerationRequest, GenerationResponse
│   │   ├── raga.py                # RagaSchema, RagaListResponse
│   │   ├── tala.py                # TalaSchema, TalaListResponse
│   │   └── common.py              # HealthResponse, ErrorDetailResponse
│   ├── services/
│   │   ├── __init__.py
│   │   ├── audio_service.py       # Audio file lifecycle, temp storage, validation
│   │   ├── raga_service.py        # Raga query service & library catalog
│   │   ├── tala_service.py        # Tala query service & rhythmic patterns
│   │   ├── generation_service.py  # Algorithmic & MIDI/synthesized composition
│   │   └── ai_service.py          # Gemini API integration with grounded prompts
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── pipeline.py            # Orchestrator running audio analysis steps
│   │   ├── preprocessor.py        # Resampling, mono conversion, loudness normalization
│   │   ├── pitch_extractor.py     # Pitch tracking (pYIN/CREPE algorithms)
│   │   ├── tonic_estimator.py     # Sa fundamental frequency estimation
│   │   ├── swara_analyzer.py      # Cent deviation mapping to Indian classical swaras
│   │   ├── raga_detector.py       # Pitch Class Distribution & Aroha/Avaroha matching
│   │   └── tala_detector.py       # Onset detection, tempo (BPM), beat grid analysis
│   └── utils/
│       ├── __init__.py
│       ├── audio_io.py            # Safe audio loading, format verification
│       ├── dataset_adapter.py     # Agnostic reader for Saraga Hindustani dataset
│       └── music_theory.py        # Swara ratios, 22 Shrutis, Thaat mappings
├── tests/
│   ├── conftest.py                # Test fixtures, dummy audio generators, test client
│   ├── test_analyze.py            # Validation, error cases, valid analysis pipeline
│   ├── test_generate.py           # Generation parameter validation & output schemas
│   ├── test_ragas_talas.py        # Catalog endpoint testing
│   ├── test_security.py           # Malicious file uploads, oversized payloads, path traversal
│   └── test_dsp_pipeline.py       # Unit tests for tonic estimation, swara mapping, pitch
├── requirements.txt               # Backend Python dependencies
└── README.md                      # Backend setup and development guide
```

---

## 3. Frontend / Backend Communication Contract

| Frontend Component | Action / Event | Target Endpoint | Payload / Method |
| :--- | :--- | :--- | :--- |
| **`AudioUploader`** | User drops/selects audio & clicks "Analyze" | `POST /api/v1/analyze` | `multipart/form-data` with `file: Binary` |
| **`AudioUploader`** | Multi-stage analysis progress polling | `GET /api/v1/analysis/{analysis_id}` | `GET` polling until `status: "completed"` |
| **`AnalysisResult`** | Render raga, tala, tempo, swaras, pitch contour | Populated from `GET /api/v1/analysis/{id}` response | JSON typed schema (`AnalysisResponse`) |
| **`CompositionGenerator`** | User configures Raga, Tala, Tempo, Duration, Creativity | `POST /api/v1/generate` | `application/json` with `GenerationRequest` |
| **`CompositionPlayer`** | Plays generated audio URL & renders waveform | Consumes `audio_url` from `GenerationResponse` | Audio streaming / static media endpoint |
| **`ThemeToggle` / `Header`** | System health & status check badge | `GET /api/v1/health` | `GET` returning API status & engine availability |

---

## 4. Security Architecture

1. **File Type Verification**: Double-layer validation with file extension check (`.mp3`, `.wav`, `.flac`, `.ogg`, `.m4a`) AND magic byte header verification using `python-magic` / audio header sniffing.
2. **File Size Limits**: Hard ceiling enforced at HTTP middleware and streaming parser level (Maximum 25 MB per recording).
3. **Temporary File Isolation & Cleanup**: Uploads stored in ephemeral isolated temp directories with UUID filenames; guaranteed deletion in `finally` blocks after feature extraction.
4. **Path Traversal Protection**: Filenames sanitized strictly using `os.path.basename` and replaced with server-generated UUIDs; no user-supplied paths reach filesystem APIs.
5. **Malicious Audio & Resource Exhaustion Defense**: Audio duration bounded (maximum 10 minutes decoded); memory-mapped streaming reads to prevent buffer overflows or zip-bomb equivalents.
6. **CORS Policy**: Configurable whitelist (`http://localhost:8080`, `http://localhost:5173`, production domains) with restricted HTTP methods (`GET`, `POST`, `OPTIONS`).
7. **Safe Error Handling**: Never expose internal stack traces, system paths, or model weights in HTTP responses; standard RFC 7807 compliant error schemas.
