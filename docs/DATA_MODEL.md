# RagaRhythm AI — Data Models & Schemas

## 1. Domain Entities & Schemas

```text
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│      Raga       │       │      Tala       │       │      Style      │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id: string      │       │ id: string      │       │ id: string      │
│ name: string    │       │ name: string    │       │ name: string    │
│ thaat: string   │       │ beats: int      │       │ description: str│
│ time: string    │       │ matras: int     │       └─────────────────┘
│ mood: string    │       │ vibhag: str     │
│ aroha: list[str]│       │ pattern: str    │
│ avaroha:list[str│       └─────────────────┘
│ vadi: string    │
│ samvadi: string │
└─────────────────┘
```

---

## 2. Analysis Data Model

### `AnalysisResult` (Domain Entity)
```python
class TonicInfo(BaseModel):
    frequency_hz: float
    note_name: str
    confidence: float

class RagaAlternative(BaseModel):
    id: str
    name: str
    confidence: float

class RagaDetectionResult(BaseModel):
    id: str
    name: str
    thaat: str
    time: str
    mood: str
    confidence: float
    aroha: list[str]
    avaroha: list[str]
    vadi: Optional[str] = None
    samvadi: Optional[str] = None
    alternatives: list[RagaAlternative] = []

class TalaDetectionResult(BaseModel):
    id: str
    name: str
    beats: int
    matras: int
    vibhag_structure: str
    theka: str
    confidence: float

class TempoResult(BaseModel):
    bpm: float
    category: str  # Vilambit (Slow), Madhyalay (Medium), Drut (Fast)

class PitchAnalysisResult(BaseModel):
    time_stamps: list[float]
    frequencies_hz: list[float]
    cents_from_tonic: list[float]
    detected_swaras: list[str]

class RhythmAnalysisResult(BaseModel):
    beat_positions_seconds: list[float]
    onset_strengths: list[float]

class AnalysisRecord(BaseModel):
    analysis_id: str
    status: Literal["pending", "preprocessing", "analyzing", "completed", "failed"]
    audio_metadata: AudioMetadata
    tonic: Optional[TonicInfo] = None
    raga: Optional[RagaDetectionResult] = None
    tala: Optional[TalaDetectionResult] = None
    tempo: Optional[TempoResult] = None
    pitch_analysis: Optional[PitchAnalysisResult] = None
    rhythm_analysis: Optional[RhythmAnalysisResult] = None
    ai_explanation: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
```

---

## 3. Composition Data Model

```python
class GenerationSettings(BaseModel):
    raga_id: str
    tala_id: str
    style_id: str
    tempo_bpm: int = Field(ge=40, le=240, default=80)
    duration_seconds: int = Field(ge=15, le=300, default=60)
    creativity_score: int = Field(ge=0, le=100, default=50)

class GeneratedComposition(BaseModel):
    composition_id: str
    raga: RagaSummary
    tala: TalaSummary
    style: StyleSummary
    tempo_bpm: int
    duration_seconds: int
    creativity_score: int
    audio_url: str
    generated_at: datetime
```

---

## 4. Frontend TypeScript Alignment

The frontend TypeScript definitions in `src/types/music.ts` align directly with backend domain models:
- TypeScript `Raga` ⟷ Backend `RagaSchema`
- TypeScript `Tala` ⟷ Backend `TalaSchema`
- TypeScript `Style` ⟷ Backend `StyleSchema`
- TypeScript `AudioAnalysis` ⟷ Backend `AnalysisResponse`
- TypeScript `CompositionSettings` ⟷ Backend `GenerationRequest`
- TypeScript `Composition` ⟷ Backend `GenerationResponse`
