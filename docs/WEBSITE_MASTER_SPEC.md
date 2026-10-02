# RagaRhythm AI — Website Rebuild Master Specification

## 1. Purpose

Rebuild **RagaRhythm AI** as a polished AI-powered Indian classical music analysis and generation web application.

The product should let a user upload an audio recording, analyze the performance, understand the detected raga/tala/rhythm, visualize musical information, and use AI to explain or generate music.

**Important:** Do not build a fake/demo-only interface that pretends analysis happened. Every feature must either be connected to a real backend/API or clearly show an honest unavailable/error state.

---

## 2. Product Goals

### Core user journey

```text
Landing Page
    ↓
Upload / Record Audio
    ↓
Audio Processing
    ↓
Music Analysis
    ├── Raga Detection
    ├── Tala / Rhythm Analysis
    ├── Tempo / BPM
    ├── Pitch / Swara Analysis
    └── Confidence
    ↓
Analysis Dashboard
    ↓
AI Explanation
    ↓
Music Generation
    ↓
Generated Audio + Visualization
```

### Primary goals

1. Make Indian classical music analysis understandable to beginners.
2. Give advanced users useful musical information and visualizations.
3. Integrate AI explanations rather than displaying raw ML output only.
4. Provide a clean path from analysis to music generation.
5. Make the application suitable for a college project demo, technical presentation, and future production deployment.

---

# 3. Website Pages

## A. Landing Page `/`

Create a premium AI/music-tech landing page.

### Hero

Headline:

> Understand. Analyze. Create.  
> Indian Classical Music with AI.

Supporting text:

> RagaRhythm AI analyzes Indian classical music, identifies musical patterns, explains ragas and rhythm, and helps you create new compositions with AI.

Primary CTA:
- **Analyze Music**

Secondary CTA:
- **Explore RagaRhythm**

### Hero visual

Use a dark music-studio aesthetic with:
- waveform
- subtle frequency visualization
- Indian classical music-inspired visual elements
- animated audio bars
- clean glass/soft-card UI

Do NOT use excessive gradients, random blobs, or generic SaaS illustrations.

### Feature cards

- Raga Detection
- Tala & Rhythm Analysis
- AI Music Explanation
- Music Generation
- Interactive Visualizations
- Audio Analysis

### How it works

```text
01 Upload
Upload a performance or audio file.

02 Analyze
AI extracts musical characteristics.

03 Understand
Explore raga, tala, tempo, pitch and rhythm.

04 Create
Generate new music using the analysis.
```

### Footer

Include:
- RagaRhythm AI
- About
- Documentation
- GitHub
- Contact
- Privacy
- Terms

---

# 4. Main Application `/app`

The application should have a persistent sidebar.

### Sidebar

- Dashboard
- Analyze Music
- Raga Library
- Rhythm / Tala
- Generate Music
- History
- Settings

Bottom:
- user/profile area
- system status

---

# 5. Dashboard

Display:

### Welcome section

> Welcome to RagaRhythm AI

CTA:
**Analyze a new recording**

### Recent analyses

Each item:

```text
Recording name
Raga
Tala
BPM
Confidence
Date
Open Analysis
```

### Quick actions

- Upload Audio
- Record Audio
- Analyze Raga
- Generate Music

### System status

Show actual backend/service status where available.

---

# 6. Audio Upload Page `/analyze`

This is one of the most important screens.

### Upload component

Support:
- MP3
- WAV
- FLAC
- M4A where backend supports it

Drag-and-drop area:

> Drop your audio here

Also provide:

**Browse files**

Optional:

**Record from microphone**

### Validation

Reject:
- unsupported format
- empty file
- corrupted audio
- excessively large file
- missing file

Display a human-readable error.

### After upload

Show:

```text
File name
Duration
Format
File size
Audio waveform
Play / Pause
Volume
```

Button:

**Start Analysis**

---

# 7. Analysis Processing Screen

Show real processing states.

Example:

```text
Uploading audio                 ✓
Pre-processing                  ✓
Extracting features             ✓
Detecting pitch                 ●
Analyzing raga                  ○
Analyzing tala                  ○
Generating AI explanation       ○
```

Never show 100% until the backend actually completes.

On failure:

```text
Analysis could not be completed.

Reason: <actual error>

Try Again
```

---

# 8. Analysis Dashboard `/analysis/[id]`

This is the core product page.

## Header

Display:

```text
<Recording Name>

Raga: <detected raga>
Tala: <detected tala>
Tempo: <BPM>
Confidence: <percentage>
```

Audio player below.

---

## Raga Detection Card

Show:

```text
Detected Raga
<Example Raga>

Confidence
92%

Alternative possibilities
<raga>
<raga>
<raga>
```

Do not fabricate confidence values.

If ML inference is unavailable, show:

> Raga detection is currently unavailable.

---

# 9. Musical Analysis

Create cards/sections for:

### Pitch

Show:
- pitch contour
- fundamental frequency
- detected notes/swaras where supported

### Swara analysis

Example format:

```text
Sa  Re  Ga  Ma  Pa  Dha  Ni
```

Use actual extracted data.

### Tempo

Show:
- BPM
- tempo category if supported

### Rhythm

Show:
- beat positions
- onset detection
- rhythm visualization

---

# 10. Tala Analysis

Display:

```text
Detected Tala
<Tala>

Confidence
<value>

Matra
<value>

Vibhag
<value>
```

Add a circular/linear rhythm visualization.

The visualization must be driven by backend data.

---

# 11. AI Explanation Panel

Use Gemini/API-backed explanation.

Title:

> Ask RagaRhythm AI

Suggested questions:

- Why was this raga detected?
- What are the characteristics of this raga?
- Explain the tala.
- What swaras are prominent?
- How can I practice this raga?
- What makes this performance different?

The AI response should be grounded in the analysis result.

Do not claim the AI listened to audio directly unless the actual implementation supports that.

---

# 12. Raga Library `/ragas`

Create a searchable library.

Each raga card can contain:

```text
Raga name
Thaat
Aroha
Avaroha
Vadi
Samvadi
Time
Description
```

Only show fields supported by the underlying dataset/source.

Search:
- raga name
- thaat
- time
- swara

---

# 13. Music Generation `/generate`

Main generation interface.

### Controls

#### Raga
Dropdown/search

#### Tala
Dropdown/search

#### Tempo
Slider/input

#### Duration
Slider/input

#### Creativity
Slider

#### Style
Options such as:
- Classical
- Meditation
- Practice
- Experimental

Only expose options actually supported by the generation backend.

### Generate button

> Generate Music

Show a real processing state.

---

# 14. Generation Result

Display:

```text
Generated Composition

Audio player
Waveform

Raga
Tala
Tempo
Duration
```

Actions:

- Play
- Pause
- Download
- Generate Again

If generation fails, show the real failure reason.

---

# 15. Visual Design System

## Theme

Preferred style:

**Premium dark music laboratory**

Use:
- near-black background
- off-white typography
- restrained purple/indigo accent
- subtle borders
- glass/blur only where useful
- rounded cards
- generous spacing

Avoid:
- excessive neon
- excessive gradients
- cartoon graphics
- generic AI robot imagery
- overcrowded dashboards

## Typography

Use a modern sans-serif such as:
- Inter
- Geist
- Manrope

Use an Indian/classical-inspired display font only sparingly.

---

# 16. Responsive Design

Must work on:

- desktop
- laptop
- tablet
- mobile

Breakpoints should be implemented intentionally.

On mobile:
- sidebar becomes a drawer/bottom navigation
- analysis cards stack
- waveform remains usable
- controls remain accessible

---

# 17. Accessibility

Required:

- keyboard navigation
- visible focus states
- semantic HTML
- accessible buttons
- accessible form labels
- sufficient contrast
- meaningful loading/error messages
- no information conveyed by color alone

---

# 18. Frontend Architecture

Preferred stack:

```text
Next.js
React
TypeScript
Tailwind CSS
```

Use reusable components.

Suggested structure:

```text
src/
├── app/
│   ├── page.tsx
│   ├── app/
│   ├── analyze/
│   ├── analysis/
│   ├── generate/
│   ├── ragas/
│   └── settings/
│
├── components/
│   ├── ui/
│   ├── audio/
│   ├── analysis/
│   ├── charts/
│   ├── dashboard/
│   └── layout/
│
├── lib/
│   ├── api/
│   ├── audio/
│   ├── validation/
│   └── utils/
│
├── hooks/
├── types/
└── styles/
```

Do not put the entire application into one giant component.

---

# 19. Backend Architecture

Preferred:

```text
Python
FastAPI
Librosa
NumPy
SciPy
TensorFlow/PyTorch where required
Gemini API
```

Suggested:

```text
backend/
├── app/
│   ├── main.py
│   ├── api/
│   ├── services/
│   │   ├── audio_service.py
│   │   ├── raga_service.py
│   │   ├── rhythm_service.py
│   │   ├── pitch_service.py
│   │   ├── generation_service.py
│   │   └── ai_service.py
│   ├── models/
│   ├── schemas/
│   └── core/
│
├── tests/
└── requirements.txt
```

---

# 20. API Contract

Initial API design:

```text
POST /api/audio/upload
POST /api/audio/analyze

GET  /api/analysis/{id}

POST /api/raga/detect
POST /api/rhythm/analyze
POST /api/pitch/analyze

POST /api/ai/explain

POST /api/music/generate

GET  /api/ragas
GET  /api/ragas/{id}

GET  /api/health
```

Use typed request/response schemas.

Never silently return fake success.

---

# 21. Data Model

An analysis result should conceptually contain:

```json
{
  "id": "analysis-id",
  "audio": {
    "filename": "recording.wav",
    "duration": 120.5,
    "format": "wav"
  },
  "raga": {
    "name": "...",
    "confidence": 0.0,
    "alternatives": []
  },
  "tala": {
    "name": "...",
    "confidence": 0.0
  },
  "tempo": {
    "bpm": 0
  },
  "pitch": {
    "contour": []
  },
  "rhythm": {
    "beats": [],
    "onsets": []
  },
  "ai_explanation": ""
}
```

Values must come from actual processing.

---

# 22. Google Cloud / AI Integration

Target architecture:

```text
Frontend
   ↓
FastAPI
   ↓
Google Cloud
   ├── Cloud Storage
   ├── Vertex AI
   ├── Gemini
   └── Cloud Run
```

Keep API keys/secrets server-side.

Never commit:

```text
.env
API keys
service account JSON
tokens
credentials
```

Provide:

```text
.env.example
```

with placeholder variable names only.

---

# 23. Error Handling

Every major operation needs:

### Loading

```text
Analyzing your recording...
```

### Success

Show actual returned result.

### Error

Show:

```text
Something went wrong.

<safe human-readable explanation>

Try Again
```

Do not expose stack traces, API keys, internal paths, or secrets to the browser.

---

# 24. Security Requirements

Test:

- malicious filenames
- unsupported file types
- huge files
- empty files
- malformed requests
- path traversal
- HTML injection
- API abuse/rate limits
- secret leakage

Never trust client-side validation alone.

---

# 25. Performance

Optimize:

- audio upload
- waveform rendering
- large analysis responses
- chart rendering
- lazy loading
- generated audio playback

Long-running analysis should not freeze the UI.

Use polling, streaming, WebSocket, or job-status architecture only when the backend actually supports it.

---

# 26. Testing Requirements

Before declaring a feature complete:

### Frontend

- component tests
- form validation
- upload validation
- loading state
- error state
- responsive behavior where practical

### Backend

- API tests
- invalid input tests
- audio validation tests
- analysis error tests
- service tests

### Required adversarial categories

At minimum cover:

1. boundary
2. malformed input
3. dependency/error failure
4. state/repeated calls
5. security

Include a property/fuzz test where a meaningful invariant exists.

---

# 27. Verification Rule

Follow the project's verification harness.

Before coding:

1. Define acceptance criteria.
2. Define critical paths.
3. Define adversarial tests.
4. Find real test/lint/typecheck/build commands.
5. Run the baseline.

After implementation:

```text
tests
adversarial tests
lint
typecheck
build
```

Run the full required checks again after the final edit.

Do not declare the website verified based only on visual inspection.

---

# 28. Acceptance Criteria

### AC1 — Landing page

Given a user opens `/`,
the page displays the RagaRhythm AI product, core value proposition, primary CTA, feature overview, and responsive navigation.

### AC2 — Audio upload

Given a supported audio file,
the application accepts it and displays valid file/audio metadata.

Given an unsupported or malformed file,
the application rejects it with a clear error.

### AC3 — Analysis

Given valid audio and an available analysis backend,
the application starts analysis and displays the returned analysis result.

If analysis fails,
the UI displays an error and does not fabricate a result.

### AC4 — Visualization

Given analysis data,
the dashboard renders the corresponding audio/tempo/pitch/rhythm visualizations.

### AC5 — AI explanation

Given a valid analysis result and available AI service,
the user can request an explanation and receive the returned response.

### AC6 — Generation

Given valid generation parameters and an available generation service,
the application starts generation and displays the resulting audio when complete.

### AC7 — Responsive UI

All primary workflows remain usable on desktop, tablet, and mobile.

### AC8 — Security

Secrets never appear in frontend source or browser responses.

### AC9 — Verification

The required tests/lint/typecheck/build commands pass after the final edit.

---

# 29. Build Order

Do NOT implement everything simultaneously.

Build in this order:

```text
STEP 1
Project setup + design system

STEP 2
Landing page

STEP 3
Application shell + sidebar

STEP 4
Audio upload

STEP 5
Audio player + waveform

STEP 6
Analysis processing state

STEP 7
Analysis dashboard

STEP 8
Raga visualization

STEP 9
Tala/rhythm visualization

STEP 10
Gemini explanation

STEP 11
Music generation

STEP 12
Raga library

STEP 13
History/settings

STEP 14
Backend integration hardening

STEP 15
Testing + security

STEP 16
Production deployment
```

---

# 30. Important Development Rules

1. Do not rewrite unrelated working code without a reason.
2. Do not create fake AI results.
3. Do not hardcode analysis results as if they came from ML.
4. Do not expose secrets.
5. Do not add dependencies without confirming they are needed.
6. Reuse components instead of duplicating UI.
7. Keep frontend and backend responsibilities separate.
8. Keep API contracts typed.
9. Handle loading, empty, success, and error states.
10. Test after meaningful changes.
11. Never say a feature is verified without fresh test/build evidence.
12. If something cannot currently be implemented because a model/API/dataset is missing, clearly mark the integration point rather than pretending it works.

---

# 31. Definition of Done

RagaRhythm AI is considered ready for the first public demo when:

- Landing page works
- User can upload audio
- Audio can be played
- Analysis workflow works end-to-end with real backend data
- Raga result is displayed when supported
- Tala/rhythm result is displayed when supported
- Pitch/tempo visualization works
- Gemini explanation works when configured
- Generation workflow works when configured
- Errors are handled cleanly
- Mobile layout works
- Secrets are protected
- Tests pass
- Build passes
- Deployment succeeds

Final verification must use real command output. If required checks cannot be executed, report:

```text
NOT VERIFIED
```

instead of claiming the application works.
