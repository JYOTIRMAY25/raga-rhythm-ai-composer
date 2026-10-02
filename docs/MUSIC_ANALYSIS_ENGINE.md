# RagaRhythm AI — Music Analysis Engine Architecture

## 1. Pipeline Lifecycle

```text
Audio File (.mp3, .wav, .flac)
   │
   ▼
[1. AudioPreprocessor]
   ├── Decoding & Mono Conversion (librosa.load, sr=22050 Hz)
   ├── Loudness Normalization (Peak / RMS)
   └── Silence Trimming
   │
   ▼
[2. TonicEstimator (Sa F0)]
   ├── Multipitch Centroid / Dominant Drone Peak Detection
   └── Continuous Sa (Tonic) Frequency Estimation in Hz
   │
   ▼
[3. PitchExtractor]
   ├── pYIN / CREPE Probabilistic Pitch Contour Extraction
   ├── Voiced Frame Probability Filtering
   └── Continuous Pitch Curve (F0 in Hz over time)
   │
   ▼
[4. SwaraAnalyzer]
   ├── Cent Conversion: Cents = 1200 * log2(F0 / Tonic_F0) mod 1200
   ├── 12-Tone Indian Chromagram / Swara Binning:
   │   (Sa=0, re=100, Re=200, ga=300, Ga=400, ma=500, Ma'=600,
   │    Pa=700, dha=800, Dha=900, ni=1000, Ni=1100 cents)
   └── Pitch Class Distribution (PCD) & Swara Prominence
   │
   ▼
[5. RagaDetector] & [6. TalaDetector] (Concurrent)
   ├── Raga Classification: PCD cosine similarity + Pakad phrase matching
   └── Tala / Rhythm: Spectral onset detection + Beat tracking + Matra alignment
   │
   ▼
[7. Confidence & Aggregator]
   └── Synthesis into typed AnalysisRecord payload
```

---

## 2. Modular Component Breakdown

### `AudioPreprocessor`
- Reads audio using `soundfile` / `librosa` into `float32` arrays.
- Standardizes sample rate to 22,050 Hz and downmixes multi-channel streams to mono.
- Performs RMS-based adaptive threshold silence stripping on boundaries.

### `TonicEstimator`
- Estimates fundamental tonic (*Sa* frequency $f_0$).
- Analyzes low-frequency spectral peaks (Tanpura drone accompaniment) across harmonic series.
- Defaults to vocal/instrumental common tonic range (120 Hz – 260 Hz).

### `PitchExtractor`
- Employs probabilistic YIN (`librosa.pyin`) or neural pitch tracking.
- Output: array of timestamps `[t_0, t_1, ...]` and corresponding frequencies `[f_0, f_1, ...]`.
- Computes voiced confidence scores per frame, rejecting unvoiced percussion noise.

### `SwaraAnalyzer`
- Normalizes pitch curve relative to detected tonic frequency.
- Maps continuous cent values to the 12 fundamental Swaras:
  `Sa, Komal Re (r), Shuddha Re (R), Komal Ga (g), Shuddha Ga (G), Shuddha Ma (m), Tivra Ma (M), Pa, Komal Dha (d), Shuddha Dha (D), Komal Ni (n), Shuddha Ni (N)`.
- Generates 12-dimensional Pitch Class Distribution (PCD) histogram.

### `TalaDetector`
- Computes spectral novelty onset envelope (`librosa.onset.onset_strength`).
- Estimates tempo (BPM) and beat positions via dynamic programming beat tracker.
- Evaluates rhythmic periodicity against canonical Hindustani Tala cycles (Teental 16, Jhaptaal 10, Ektaal 12, Rupak 7, Dadra 6, Keherwa 8).

### `RagaDetector`
- Evaluates similarity between extracted PCD and ground-truth theoretical PCD profiles.
- Analyzes ascending (*aroha*) and descending (*avaroha*) transition probabilities.
- Computes calibrated confidence intervals and ranks alternative potential ragas.
