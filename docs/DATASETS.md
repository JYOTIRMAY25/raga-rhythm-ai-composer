# Datasets & Audio Corpus Setup

This document details the external datasets utilized by **RagaRhythm AI**, specifically the **Saraga Hindustani Dataset (v1.5)**, along with instructions for downloading, directory structure layout, and verification.

---

## 1. Saraga Hindustani Music Dataset (v1.5)

RagaRhythm AI utilizes the open-access **Saraga Hindustani Dataset** developed by the Music Technology Group (MTG) at Universitat Pompeu Fabra (UPF) and the CompMusic Project.

- **Primary Reference**: [Saraga Dataset - MTG UPF](https://mtg.github.io/saraga/)
- **Repository**: [Zenodo / MTG Saraga Hindustani Collection](https://zenodo.org/record/3887095)
- **License**: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)

---

## 2. Directory Structure & Discovery

RagaRhythm AI includes an automated dataset adapter ([`backend/app/utils/dataset_adapter.py`](file:///d:/raga-rhythm-ai-composer-main/backend/app/utils/dataset_adapter.py)) that discovers Saraga tracks dynamically.

To configure local audio tracks for training, evaluation, or offline analysis, place the extracted dataset in either of the following paths:

```text
raga-rhythm-ai-composer/
├── saraga1.5_hindustani/              <-- Standard Root Location
│   └── ... (artist/track folders)
└── data/
    └── saraga1.5_hindustani/          <-- Alternative Subdirectory
```

### Track Annotation Layout

Each track within the Saraga collection consists of synchronized multitrack audio and annotations:

```text
[Track_Folder]/
├── [track_name].mp3.mp3                  # Audio (Vocal / Instrumental mix)
├── [track_name].pitch.csv                # Continuous F0 Pitch Contour
├── [track_name].cttempo.bpm.csv          # Tempo / BPM Annotations
├── [track_name].sama.time.csv            # Tala Sam Markers & Cycle Boundaries
├── [track_name].sections-pcode.time.csv  # Musical Section Form (Alap, Jor, Bandish)
├── [track_name].phrases-pcode.time.csv   # Annotated Melodic Phrases / Pakads
└── [track_name].metadata.json            # Raga, Tala, Artist, Tonic (Sa Hz) metadata
```

---

## 3. Dataset Adapter Capabilities

The adapter ([`SaragaDatasetAdapter`](file:///d:/raga-rhythm-ai-composer-main/backend/app/utils/dataset_adapter.py)) performs:
1. **Multi-location Auto-discovery**: Detects root directories across project and data paths.
2. **Lazy-loading & Caching**: Efficiently parses pitch contours and phrase segments only on demand to maintain minimal memory overhead.
3. **Raga & Tala Canonical Normalization**: Maps diverse transcription spellings (e.g. `Bhairavi`, `raga_bhairav`, `TeenTaal`, `Tintal`) into unified internal canonical identifiers.
4. **Adversarial & Path Traversal Protection**: Rejects `..` path injections and ignores hidden/system files (e.g. `._*`, `.DS_Store`, `__MACOSX`).

---

## 4. Dataset Verification

Run the automated dataset adapter test suite to verify track parsing:

```bash
python -m pytest tests/backend/test_dataset_adapter.py -v
```
