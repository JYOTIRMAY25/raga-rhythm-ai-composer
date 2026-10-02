# RagaRhythm AI Composer

**RagaRhythm AI** is a production-grade Indian Classical Music (ICM) analysis and algorithmic composition platform. It features DSP analysis, microtonal Shruti intonation, multi-timbral synthesis, and deterministic symbolic composition across **70 Ragas** and **9 Talas**.

---

## Key Features

- **Audio Analysis Engine**:
  - Multi-harmonic Pitch Extraction (YIN + HPS).
  - Robust fundamental Tonic ($S_a$) estimation and validation.
  - Continuous Pitch Class Distribution (PCD) and swara recognition with microtonal deviation tracking.
  - Melodic phrase segmentation, characteristic motif (*pakad*) matching, and aroha/avaroha adherence.
  - Tala cycle classification across canonical Hindustani rhythm structures.

- **Algorithmic Composition Engine**:
  - Deterministic generation across **70 Ragas** and **9 Talas** (630 canonical combinations, 7,560 verified structures).
  - Strict adherence to classical rules: Vadi/Samvadi hierarchy, forbidden swaras (*varjit*), non-linear movement (*vakra*), and Sam landing points.
  - Full structural progression (*sthayi*, *antara*, *taan*, *jhala*).

- **Microtonal Shruti Tuning & Timbral Synthesis**:
  - 22-Shruti mathematical intonation ratios (Pramana, Dvitiya, Trishruti, Chatushruti).
  - Natural micro-ornaments (*meend* glides, *gamak* heavy oscillations, *andolan* slow wavelets, *kan* grace notes).
  - Multi-timbral acoustic modeling (Bansuri flute, Shehnai reed, Sitar plucked, Sarod resonating, Tanpura drone layer, Ensemble).
  - Clean 16-bit 22.05 kHz PCM WAV export.

- **Production Performance & Caching**:
  - Deterministic bounded LRU caching for compositions and WAV audio (`AUDIO_RENDERER_VERSION = "1.0"`).
  - Thread-safe concurrency architecture tested under multi-client loads.
  - Request ID tracing middleware, latency logging, and structured error responses.
  - Fully containerized with multi-stage Docker and Cloud Run readiness.

---

## Architecture Overview

```text
┌────────────────────────────────────────────────────────┐
│                   React 18 Frontend                    │
│   (TypeScript / Vite / TailwindCSS / Radix UI / Tone)   │
└───────────────────────────┬────────────────────────────┘
                            │ HTTP / JSON / WAV
┌───────────────────────────▼────────────────────────────┐
│                    FastAPI Backend                     │
│  ┌─────────────────────────┐ ┌───────────────────────┐  │
│  │    Audio Analysis DSP   │ │  Composition Engine   │  │
│  │ (YIN / HPS / Swara/Tala)│ │  (70 Ragas × 9 Talas) │  │
│  └─────────────────────────┘ └───────────┬───────────┘  │
│  ┌─────────────────────────┐             │              │
│  │ Bounded LRU Cache (Mem) │ ┌───────────▼───────────┐  │
│  │(SHA-256 / Bounded Mem)  │ │   Timbral Synthesizer │  │
│  └─────────────────────────┘ │  (Shruti / 16-bit PCM)│  │
│                              └───────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

---

## Supported Musicological Matrix

### Ragas (70 Classical Ragas)
*Abhogi, Ahir Bhairav, Asavari, Bageshri, Bahar, Bairagi, Basanti Kedar, Bhairav, Bhairavi, Bhatiyar, Bhimpalasi, Bhoopali, Bibhas, Bihag, Bilaskhani Todi, Chandrakauns, Dagori Deepki, Desh, Dhani, Durga, Gaud Malhar, Gauri, Gawti, Hameer, Hindol Pancham, Jaijaiwanti, Jait Kalyan, Jaunpuri, Jog, Jogiya, Kafi, Kalavati, Kedar, Khamaj, Khat, Khokar, Kirwani, Komal Rishabh Asavari, Lagan Gandhar, Lalit, Lalit Pancham, Madhukauns, Malkauns, Maru Bihag, Marwa, Megh, Mian Malhar, Mishra Kalingada, Mishra Piloo, Multani, Nat Bhairav, Nat Kamod, Paraj, Poorva, Puriya, Puriya Dhanashree, Rageshree, Ramdasi Malhar, Saraswati, Sawani, Shankara, Shree, Shuddh Sarang, Shuddha Kalyan, Sohani, Suha, Tilak Kamod, Todi, Triveni Gauri, Yaman.*

### Talas (9 Classical Rhythm Cycles)
- **Teentaal** (16 beats: 4+4+4+4)
- **Ektaal** (12 beats: 2+2+2+2+2+2)
- **Jhaptaal** (10 beats: 2+3+2+3)
- **Rupak** (7 beats: 3+2+2)
- **Keherwa** (8 beats: 4+4)
- **Dadra** (6 beats: 3+3)
- **Chautaal** (12 beats: 2+2+2+2+2+2)
- **Dhamar** (14 beats: 5+2+3+4)
- **Tilwada** (16 beats: 4+4+4+4)

---

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm
- (Optional) Docker for containerized deployment

### 1. Environment Setup

Copy `.env.example` to create your local environment file:

```bash
cp .env.example .env
```

Set any optional API keys in `.env` (e.g. `GEMINI_API_KEY` for AI musicological explanations).

### 2. Backend Startup

```bash
# Install Python dependencies
pip install -r backend/requirements.txt

# Launch FastAPI development server
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend API documentation is available at `http://localhost:8000/docs`.

### 3. Frontend Startup

```bash
# Install NPM dependencies
npm install

# Start Vite development server
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Verification & Testing Suite

Run the complete regression test suite:

```bash
# Backend test suite (291 tests)
python -m pytest tests/backend/ -v

# Full 70 Raga × 9 Tala composition validation matrix (630 combinations / 7,560 compositions)
python scripts/validate_compositions.py

# Production performance & latency benchmark
python scripts/benchmark_production.py

# Frontend test suite (59 tests)
npm test -- --run

# TypeScript check & ESLint
npx tsc --noEmit
npm run lint

# Production build
npm run build
```

---

## Docker & Production Deployment

### Build & Run Container

```bash
docker build -t ragarhythm-backend .
docker run -p 8000:8000 --env-file .env ragarhythm-backend
```

For complete deployment details including Google Cloud Run, see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

---

## Datasets & Audio Corpus

For instructions on integrating the **Saraga Hindustani Dataset**, refer to [docs/DATASETS.md](docs/DATASETS.md).
