# RagaRhythm AI — Rhythm & Tala Engine Specification

## 1. Tala Analysis Architecture

Hindustani rhythmic structures (*Talas*) are cyclical patterns characterized by:
- **Avartan**: One complete rhythmic cycle.
- **Matras**: Total count of beats in the cycle (e.g., 16 for Teental, 10 for Jhaptaal).
- **Vibhags**: Sub-divisions (measures) of beats (e.g., $4+4+4+4$ or $2+3+2+3$).
- **Sam**: The primary accent / first beat of the cycle ($+1$).
- **Khali**: The unaccented / open wave marker (usually mid-cycle, denoted by $0$).
- **Theka**: Canonical spoken mnemonic drum syllables (*bols*).

---

## 2. Detection Flow

```text
Audio Waveform
   │
   ▼
Spectral Novelty Function (Onset Envelope)
   │
   ▼
Tempo (BPM) & Beat Tracker (Dynamic Programming)
   │
   ▼
Beat Interval Periodicity & Autocorrelation
   │
   ▼
Matra Cycle Fit Evaluation (16, 12, 10, 8, 7, 6 beats)
   │
   ▼
Tala Scoring & Confidence Output
```

---

## 3. Visualization Data Payload

The Tala Engine emits structured coordinate payloads consumable directly by the frontend circular/linear rhythm visualizer:

```json
{
  "tala_name": "Teental",
  "matras": 16,
  "vibhag_structure": [4, 4, 4, 4],
  "sam_position": 1,
  "khali_positions": [9],
  "tali_positions": [1, 5, 13],
  "theka_syllables": [
    "Dha", "Dhin", "Dhin", "Dha",
    "Dha", "Dhin", "Dhin", "Dha",
    "Dha", "Tin", "Tin", "Ta",
    "Ta", "Dhin", "Dhin", "Dha"
  ],
  "estimated_bpm": 72.4,
  "confidence": 0.85
}
```

---

## 4. Tala Knowledge Base (`backend.app.analysis.tala_knowledge_base`)

### 4.1 Domain Model (`TalaDefinition`)
Strongly-typed, immutable Pydantic model (`frozen=True`) representing canonical Hindustani rhythmic cycles.

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Canonical display name (e.g. `"Teental"`) |
| `tala_id` | `str` | Normalized snake_case ID (e.g. `"teental"`) |
| `aliases` | `List[str]` | Alternative spellings and transliterations |
| `matras` | `int` | Total count of beats in one cycle |
| `vibhag_structure` | `List[int]` | Measure partitions (e.g. `[4, 4, 4, 4]`) |
| `sam_position` | `int` | 1-indexed beat position of Sam (default: `1`) |
| `khali_positions` | `List[int]` | 1-indexed beat positions of Khali (open wave) |
| `tali_positions` | `List[int]` | 1-indexed beat positions of Tali (claps) |
| `theka_syllables` | `List[str]` | Canonical bols of length equal to `matras` |
| `description` | `Optional[str]` | Contextual musicological notes |

### 4.2 Invariant Validation Rules
1. `name` and `tala_id` must be non-empty strings.
2. `matras > 0`.
3. $\sum(\text{vibhag\_structure}) == \text{matras}$, with each $\text{vibhag} > 0$.
4. $\text{len}(\text{theka\_syllables}) == \text{matras}$, with every syllable non-empty.
5. $1 \le \text{sam\_position} \le \text{matras}$.
6. $1 \le \text{khali\_position} \le \text{matras}$ with no duplicate positions.
7. $1 \le \text{tali\_position} \le \text{matras}$ with no duplicate positions.
8. `khali_positions` and `tali_positions` must be mutually disjoint.

### 4.3 Initial Hindustani Talas Supported
1. **Teental** (16 beats, $[4,4,4,4]$, Sam: 1, Khali: [9], Tali: [1, 5, 13])
2. **Dadra** (6 beats, $[3,3]$, Sam: 1, Khali: [4], Tali: [1])
3. **Keharwa** (8 beats, $[4,4]$, Sam: 1, Khali: [5], Tali: [1])
4. **Rupak** (7 beats, $[3,2,2]$, Sam: 1, Khali: [1], Tali: [4, 6] — *begins with Khali on Sam*)
5. **Jhaptaal** (10 beats, $[2,3,2,3]$, Sam: 1, Khali: [6], Tali: [1, 3, 8])
6. **Ektaal** (12 beats, $[2,2,2,2,2,2]$, Sam: 1, Khali: [3, 7], Tali: [1, 5, 9, 11])

### 4.4 Knowledge Base Lookup APIs
- `get_tala(name: str) -> Optional[TalaDefinition]`: Resilient, case-insensitive, diacritic-tolerant lookup resolving canonical names, IDs, and aliases.
- `get_all_talas() -> List[TalaDefinition]`: Returns all registered talas.
- `get_talas_by_matras(matras: int) -> List[TalaDefinition]`: Filters talas by beat count.
- `has_tala(name: str) -> bool`: Checks existence.
- `normalize_tala_lookup_key(name: Optional[str]) -> str`: Normalizes raw names for indexing.

---

## 5. Rhythm Feature Extraction (`backend.app.analysis.rhythm_analyzer`)

### 5.1 Architecture & Algorithms

1. **Spectral Novelty Function**:
   - **STFT Configuration**: Hann window, $N_{FFT} = 1024$, hop size $H = 220$ samples at $f_s = 22050\text{ Hz}$ ($\approx 100.23\text{ fps}$ temporal resolution).
   - **Log-Magnitude Compression**: $S(f, t) = \log(1 + 10 \cdot |X(f, t)|)$.
   - **Rectified Spectral Flux**: $\Delta S(f, t) = \max(0, S(f, t) - S(f, t-1))$.
   - **Novelty Envelope**: $O(t) = \sum_f \Delta S(f, t)$.
   - **Adaptive Detrending & Normalization**: Baseline subtracted via a 250ms rolling window and normalized to $[0.0, 1.0]$. Pure silence and non-finite signals are safely sanitized.

2. **Adaptive Onset Peak Detection**:
   - **Local Thresholding**: $T(t) = \mu_{local}(t) + \delta_{onset}$ (default $\delta = 0.08$).
   - **Refractory Spacing**: Minimum inter-onset distance $\Delta t_{min} = 60\text{ ms}$ to suppress double-triggering on single percussion strokes.
   - **Outputs**: Frame indices (`onset_frames`) and timestamps (`onset_times`).

3. **Inter-Onset Interval (IOI) Analysis**:
   - **IOI Sequence**: $\text{IOI}_k = t_{k+1} - t_k$ for valid $t_{k+1} > t_k$.
   - **Robust Summary Statistics**: Median IOI, mean IOI, standard deviation, Interquartile Range (IQR), and Median Absolute Deviation (MAD).

4. **Autocorrelation & Multi-Cue BPM Estimation**:
   - **Tempo Search Window**: Evaluates candidate tempos within $[30.0, 360.0]\text{ BPM}$.
   - **Tempo Prior Weighting**: Log-normal distribution centered at $120.0\text{ BPM}$ ($\sigma = 1.0\text{ octave}$) to balance half/double-tempo ambiguities.
   - **IOI Cross-Validation**: Reconciles envelope autocorrelation with onset interval statistics to ensure the fundamental pulse is selected over higher harmonic lags.
   - **Sub-Lag Interpolation**: Parabolic interpolation around the candidate peak for sub-frame temporal precision.
   - **Confidence Estimation**: Weighted combination of autocorrelation peak contrast and onset IOI regularity (coefficient of variation). For silence or non-periodic signals, `estimated_bpm = None` and `confidence = 0.0`.

### 5.2 Domain Model (`RhythmFeatures`)
| Field | Type | Description |
|---|---|---|
| `novelty_envelope` | `np.ndarray` | 1D float32 normalized onset novelty curve |
| `novelty_times` | `np.ndarray` | 1D float64 frame timestamps (seconds) |
| `onset_times` | `np.ndarray` | 1D float64 detected onset peak timestamps |
| `onset_frames` | `np.ndarray` | 1D int64 detected onset peak frame indices |
| `ioi_intervals` | `np.ndarray` | 1D float64 positive inter-onset intervals |
| `estimated_bpm` | `Optional[float]` | Estimated tempo (BPM) or `None` if insufficient evidence |
| `tempo_confidence` | `float` | Estimation confidence in $[0.0, 1.0]$ |
| `frame_rate` | `float` | Novelty analysis frame rate ($\approx 100.2\text{ Hz}$) |
| `hop_length` | `int` | STFT hop length in samples ($220$) |
| `sample_rate` | `int` | Audio sample rate ($22050\text{ Hz}$) |
| `duration_seconds` | `float` | Total audio duration analyzed |
| `statistics` | `Dict[str, Any]` | Detailed IOI and autocorrelation diagnostics |

---

## 6. Beat Grid & Matra Alignment (`backend.app.analysis.beat_tracker`)

### 6.1 Architecture & Algorithms

1. **Dynamic Programming Beat Tracking**:
   - Computes cumulative objective function across onset novelty frames:
     $$D[t] = O[t] + \max_{\delta} \left( D[t - \delta] - \alpha \cdot \left(\log \frac{\delta}{\tau}\right)^2 \right)$$
     where $\delta \in [0.5\tau, 2.0\tau]$ and $\alpha = 100.0$.
   - Recovers regular beat pulses across missing percussive onsets and filters out rapid subdivisions / ornamentation strokes.

2. **Explicit Multi-Hypothesis Tempo Evaluation**:
   - Evaluates candidate tempo multipliers: $0.5\times$ (half-tempo/vilambit), $1.0\times$ (nominal tempo), and $2.0\times$ (double-tempo/drut).
   - Scores hypotheses based on total onset energy coverage ($\frac{\sum O(b_i)}{\sum O(t)}$), inter-beat interval regularity, and alignment contrast.
   - Exposes candidate scores in `tempo_hypotheses: Dict[str, float]` and selected choice in `selected_hypothesis`.

3. **Cyclic Matra Alignment & Sam Phase Estimation**:
   - For an arbitrary cycle length $M$ (e.g. $16, 12, 10, 8, 7, 6$ matras):
   - Evaluates cycle phase offsets $k \in \{0, \dots, M-1\}$ maximizing boundary accent energy:
     $$k_{sam} = \arg\max_k \frac{1}{N_{cycles}} \sum_{j} O(t_{j \cdot M + k})$$
   - Maps tracked beats to 1-indexed matra numbers: $\text{matra}[i] = (i - k_{sam}) \pmod M + 1$.
   - Computes continuous cycle phase $\phi[i] = ((i - k_{sam}) \pmod M) / M \in [0.0, 1.0)$.
   - Emits candidate `sam_timestamps` for cycle boundaries.

### 6.2 Domain Model (`BeatGrid`)
| Field | Type | Description |
|---|---|---|
| `beat_times` | `np.ndarray` | 1D float64 tracked beat timestamps (seconds) |
| `beat_frames` | `np.ndarray` | 1D int64 frame indices for each beat |
| `beat_period` | `float` | Estimated median interval between beats (seconds) |
| `bpm` | `Optional[float]` | Tempo derived from tracked beat grid |
| `confidence` | `float` | Beat tracking confidence in $[0.0, 1.0]$ |
| `phase_offset_sec` | `float` | Initial beat phase timestamp (seconds) |
| `tempo_hypotheses` | `Dict[str, float]` | Relative scores for candidate multipliers (`"0.5x"`, `"1.0x"`, `"2.0x"`) |
| `selected_hypothesis` | `str` | Selected multiplier (e.g. `"1.0x"`) |
| `matra_indices` | `Optional[np.ndarray]` | 1-indexed matra numbers ($1 \dots M$) |
| `cycle_phases` | `Optional[np.ndarray]` | Normalized cycle phase in $[0.0, 1.0)$ |
| `sam_timestamps` | `Optional[np.ndarray]` | Timestamps corresponding to Matra 1 (Sam) |
| `cycle_length` | `Optional[int]` | Active cycle length ($M$) |
| `diagnostics` | `Dict[str, Any]` | Tracking and regularity diagnostics |

---

## 7. Tala Classification & Scoring (`backend.app.analysis.tala_classifier`)

### 7.1 Architecture & Multi-Cue Evidence Scoring

The Tala classifier evaluates 9 target Hindustani rhythmic structures:
1. **Teentaal** (16 matras, $[4,4,4,4]$, Sam: 1, Khali: [9], Tali: [1, 5, 13])
2. **Ektaal** (12 matras, $[2,2,2,2,2,2]$, Sam: 1, Khali: [3, 7], Tali: [1, 5, 9, 11])
3. **Jhaptaal** (10 matras, $[2,3,2,3]$, Sam: 1, Khali: [6], Tali: [1, 3, 8])
4. **Tilwada** (16 matras, $[4,4,4,4]$, Vilambit laya)
5. **Jhoomra** (14 matras, $[3,4,3,4]$, Vilambit laya)
6. **Jatt / Addha** (16 matras, $[4,4,4,4]$, Madhya/Drut laya)
7. **Rupak** (7 matras, $[3,2,2]$, Sam is Khali, Tali: [4, 6])
8. **Keherwa** (8 matras, $[4,4]$, Sam: 1, Khali: [5], Tali: [1])
9. **Dadra** (6 matras, $[3,3]$, Sam: 1, Khali: [4], Tali: [1])

#### Scoring Components:
- **Cycle Periodicity Fit ($S_{cycle}$)**: Normalized novelty envelope autocorrelation at lag $M \cdot \tau_{beat}$.
- **Structural Accent Fit ($S_{accent}$)**: Evaluates energy contrast between Tali positions and Khali positions (adapted for Rupak where Sam is Khali).
- **Laya Compatibility ($S_{laya}$)**: Log-normal tempo likelihood across typical Hindustani performance speeds (Vilambit, Madhya, Drut).
- **Vibhag Symmetry ($S_{vibhag}$)**: Partition consistency score.
- **Ambiguity & Decision Policy**: Emits ranked candidates with temperature-scaled posterior confidences without forcing an invalid guess when evidence is ambiguous.

### 7.2 Domain Models (`TalaCandidate`, `TalaClassificationResult`)
| Field | Type | Description |
|---|---|---|
| `predicted_tala` | `Optional[str]` | Top-1 predicted Tala name (e.g. `"Teentaal"`), or `None` |
| `predicted_tala_id` | `Optional[str]` | Top-1 predicted Tala ID (e.g. `"teental"`) |
| `predicted_matras` | `Optional[int]` | Cycle beat count ($M$) |
| `confidence` | `float` | Overall classification confidence $[0.0, 1.0]$ |
| `is_ambiguous` | `bool` | Flag indicating closely contested top candidates |
| `candidates` | `List[TalaCandidate]` | Ranked candidate list with component scores |
| `estimated_bpm` | `Optional[float]` | Active tempo |
| `tempo_hypothesis` | `str` | Chosen tempo multiplier (`"1.0x"`, `"0.5x"`, `"2.0x"`) |
| `sam_phase_sec` | `Optional[float]` | Timestamp of first detected Sam |




