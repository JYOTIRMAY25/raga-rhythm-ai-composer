# RagaRhythm AI — Raga Detection Engine & Dataset Adapter

## 1. Detection Architecture

Raga detection in Indian classical music requires analyzing beyond static Western pitch scales:
1. **Pitch Class Distribution (PCD)**: Continuous histogram of pitch presence normalized to tonic *Sa*.
2. **Pitch Class Dyad Distribution (PCDD)**: Transition frequencies between adjacent swara pairs (capturing characteristic movements such as `G-M-R-S` or `N-r-S`).
3. **Melodic Phrase (*Pakad*) Recognition**: Sequential motif matching against distinctive identifier phrases.
4. **Vadi / Samvadi Prominence**: Temporal duration and stability weighting on dominant notes.

---

## 2. Dataset Integration Architecture (Saraga Hindustani)

The Saraga Hindustani dataset provides multi-track audio, tonic annotations, raga metadata, and beat annotations.

### Agnostic Dataset Adapter Interface
To avoid hardcoding or assuming uninspected folder structures, the backend defines an abstract adapter:

```python
from abc import ABC, abstractmethod
from typing import Iterator, Dict, Any, Optional

class DatasetSample(BaseModel):
    sample_id: str
    audio_path: str
    raga_name: Optional[str]
    tala_name: Optional[str]
    tonic_hz: Optional[float]
    metadata: Dict[str, Any]

class BaseDatasetAdapter(ABC):
    @abstractmethod
    def scan_dataset(self, dataset_root: str) -> list[str]:
        """Discover available audio and annotation files without assuming fixed layout."""
        pass

    @abstractmethod
    def load_sample(self, sample_id: str) -> DatasetSample:
        """Extract audio stream and available ground truth annotations."""
        pass

    @abstractmethod
    def iter_samples(self) -> Iterator[DatasetSample]:
        """Iterate through validated dataset samples."""
        pass
```

---

## 3. Confidence Calculation

Confidence is computed using a normalized composite metric:
$$\text{Confidence} = w_1 \cdot S_{\text{PCD}} + w_2 \cdot S_{\text{Pakad}} + w_3 \cdot S_{\text{Vadi}}$$
where:
- $S_{\text{PCD}}$: Cosine similarity of pitch histogram against raga template.
- $S_{\text{Pakad}}$: Sequence alignment score of detected melodic phrases.
- $S_{\text{Vadi}}$: Ratio of energy spent on primary sonant note (*Vadi*).
- $w_1 = 0.5, w_2 = 0.3, w_3 = 0.2$ default weights.
