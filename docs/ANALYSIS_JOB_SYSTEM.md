# Analysis Job System Architecture & Reference

## 1. Overview & Primary Objective

The Analysis Job System in RagaRhythm AI transitions the compute-heavy Digital Signal Processing (DSP) audio analysis pipeline from a blocking, long-lived synchronous HTTP request into an asynchronous, bounded in-process job execution workflow.

### Key Goals:
- Immediate HTTP acknowledgment: `POST /api/v1/analyze` yields an unpredictable `job_id` within milliseconds.
- Non-blocking I/O: FastAPI's event loop remains fully responsive for unrelated API requests.
- Real-time visibility: Fine-grained, monotonic progress tracking (0–100%) mapped across canonical DSP pipeline stages.
- Cooperative cancellation: Safe early termination of in-flight processing at stage boundaries.
- Resource safety: Bounded retention, isolated temporary file management, and proactive cleanup on all exit paths.

---

## 2. Job Lifecycle & State Machine

```text
       ┌───────────┐
       │   POST    │
       │  /analyze │
       └─────┬─────┘
             │ (create_job)
             ▼
       ┌───────────┐
       │  QUEUED   ├──────────────┐
       └─────┬─────┘              │
             │ (worker start)     │ (cancel)
             ▼                    │
      ┌─────────────┐             │
      │ PROCESSING  │             │
      └──┬───────┬──┘             │
         │       │ (cancel req)   │
(success)│       └────────────┐   │
         ▼                    ▼   ▼
   ┌───────────┐         ┌───────────┐
   │ COMPLETED │         │ CANCELLED │
   └───────────┘         └───────────┘
         ▲
         │ (error)
   ┌─────┴─────┐
   │  FAILED   │
   └───────────┘
```

### Job States:
1. **QUEUED**: Job created and placed in the in-memory registry; awaiting worker thread execution.
2. **PROCESSING**: Worker thread picked up the job; active DSP analysis is underway across pipeline stages.
3. **COMPLETED**: Terminal state. Full `AnalysisResponse` payload computed and stored. Progress is strictly 100%.
4. **FAILED**: Terminal state. An unhandled exception occurred or audio could not be analyzed. Contains sanitized `JobError`.
5. **CANCELLED**: Terminal state. Explicitly cancelled by client before or during processing. Progress frozen at time of cancellation.

---

## 3. Progress Tracking Semantics

Progress updates are emitted strictly at meaningful DSP pipeline stage boundaries. Low-level DSP sample/frame loops are never modified for progress reporting, ensuring zero impact on numerical precision and algorithm determinism.

| Progress Range (%) | Pipeline Stage | Description |
|---|---|---|
| **0 – 5** | Initialization | Input validation, audio decoding, temp file creation |
| **5 – 15** | Audio preprocessing | Resampling (22.05 kHz mono), RMS normalization |
| **15 – 30** | Tonic estimation | Multi-octave candidate extraction, Sa fundamental F0 |
| **30 – 50** | Pitch extraction | Time-series f0 contour extraction (pYIN / CREPE) |
| **50 – 60** | Tonic resolution | Joint refinement of Sa frequency against pitch trajectory |
| **60 – 70** | Swara analysis | Pitch-to-cent deviation mapping, Indian scale quantization |
| **70 – 80** | Raga detection | Pitch Class Distribution (PCD) & Aroha/Avaroha matching |
| **80 – 90** | Rhythm / beat analysis | Onset envelope detection, beat tracker, tempo estimation |
| **90 – 98** | Tala classification | Vibhag structure & theka metric cycle identification |
| **98 – 100** | Finalization / Completed | Assembly of structured analysis schema and explanation |

### Progress Invariants:
- Monotonic: `progress(t_1) >= progress(t_0)` for all valid timestamps.
- Bounded: `0 <= progress <= 100`.
- Terminal-only 100%: Progress can only reach `100` when the status transitions to `COMPLETED`. Failed or cancelled jobs never report `100%`.
- Fault-tolerant callbacks: Any failure within a progress callback does not crash or interrupt the underlying DSP pipeline.

---

## 4. Execution Model & Concurrency

### Why In-Process `ThreadPoolExecutor`?
- **GIL Release in NumPy / SciPy**: Heavy audio calculations (FFT, filtering, linear algebra, pYIN autocorrelation) execute in optimized C/Fortran routines that release the Python GIL, yielding multi-core speedup without multiprocessing overhead.
- **Zero Serialization Penalty**: Large audio buffers and pitch contours do not require costly inter-process communication (IPC) pickling.
- **Cross-Platform Compatibility**: Avoids multiprocessing spawn issues on Windows.
- **Thread Safety**: State transitions are synchronized using Python's `threading.RLock`.

### Concurrency & Queue Bounds:
- `max_analysis_workers` (Default: 4): Maximum concurrent worker threads executing DSP pipelines.
- `max_queued_jobs` (Default: 20): Maximum pending jobs in queue. Additional submissions receive HTTP 429 (`QUEUE_FULL`).
- `job_retention_seconds` (Default: 3600s / 1 hr): Completed and failed jobs are evicted after TTL expiry.
- `max_retained_jobs` (Default: 100): Hard memory cap on total job records stored in the manager.

---

## 5. File Safety & Isolation

1. **Unique Ephemeral Paths**: Each upload generates an isolated temporary file using UUID4 naming in the OS temp directory (`app_temp_audio_*.tmp`).
2. **Deterministic Cleanup**:
   - On completion: Audio file unlinked immediately after final stage.
   - On failure: Safe unlinking in the `finally` block of the worker thread.
   - On cancellation: Temporary files purged during cancellation handling.
   - On application shutdown: Cleanup invoked during FastAPI lifespan shutdown.
3. **Security Invariants Preserved**:
   - Magic-byte audio verification (MP3, WAV, FLAC, OGG, M4A).
   - 25 MB file size limit enforced during streaming read.
   - Path traversal prevention using strict basename sanitization.

---

## 6. Error Sanitization & Security

All worker errors are caught and transformed into sanitized `JobError` models:
- **Internal Details Concealed**: No stack traces, file paths, or private host environment variables are exposed to clients.
- **Client-Safe Error Codes**: Standard error codes such as `EMPTY_AUDIO`, `INVALID_AUDIO_FORMAT`, `DSP_TIMEOUT`, `ANALYSIS_FAILED`.
- **Unpredictable Identifiers**: UUID4 job IDs prevent sequential enumeration and IDOR attacks.

---

## 7. In-Process Limitations & Future Persistent Architecture

### In-Process Model Limitations:
- **Process Lifetime Bound**: Jobs are stored in memory; restarting the server process clears active and retained jobs.
- **Single-Instance Only**: Job state is not shared across multiple horizontal FastAPI worker instances.

### Future Persistent Scaling Path:
When moving to horizontally scalable multi-server production infrastructure:
1. Replace `backend/app/jobs/manager.py` backend with Redis / Celery / BullMQ queue broker.
2. Store job status records and results in PostgreSQL or Redis with TTL.
3. Store temporary audio payloads in S3-compatible object storage (e.g., AWS S3, MinIO).
4. Worker processes run independently in containerized pods with auto-scaling based on queue depth.
5. The API contract (`POST /analyze`, `GET /analysis/{job_id}`, `POST /analysis/{job_id}/cancel`) and frontend polling hooks remain identical.
