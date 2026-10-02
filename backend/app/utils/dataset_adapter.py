"""
Saraga Hindustani Dataset Adapter for RagaRhythm AI.

Provides type-safe, read-only discovery, validation, and lazy-loading for the
Saraga Hindustani 1.5 music dataset.
"""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# Domain Models & Annotation Payloads
# ============================================================================

class PitchContourData(BaseModel):
    """Continuous F0 pitch contour points extracted at ~225 Hz."""
    time_stamps: List[float] = Field(..., description="Timestamps in seconds")
    frequencies_hz: List[float] = Field(..., description="Fundamental frequencies in Hz (0.0 for unvoiced)")

    @property
    def total_frames(self) -> int:
        return len(self.time_stamps)

    @property
    def voiced_frames(self) -> int:
        return sum(1 for f in self.frequencies_hz if f > 0.0)


class TempoAnnotation(BaseModel):
    """Detailed tempo and meter ground truth."""
    bpm: float
    beat_duration_s: float
    matra_duration_s: float
    matras_per_cycle: int
    start_s: float
    end_s: float


class BpmAnnotation(BaseModel):
    """Segmented BPM ground truth."""
    bpm: float
    start_s: float
    end_s: float


class SectionAnnotation(BaseModel):
    """Structural/performance section annotation (e.g., Alap, Khayal Vilambit)."""
    start_s: float
    section_index: int
    duration_s: float
    label: str


class MelodicPhraseAnnotation(BaseModel):
    """Pakad / characteristic melodic phrase swara motif annotation."""
    onset_s: float
    voiced_flag: int
    duration_s: float
    phrase_swaras: str


class SaragaTrackAnnotations(BaseModel):
    """Complete structured metadata and annotation pointers for a Saraga track."""
    sample_id: str = Field(..., description="Unique track identifier (MBID or relative path)")
    album_name: str
    track_title: str
    audio_path: str = Field(..., description="Path to the .mp3.mp3 audio waveform file")
    mbid: Optional[str] = None
    tonic_hz: Optional[float] = None
    raga_names: List[str] = Field(default_factory=list, description="Original raga names from Saraga JSON")
    normalized_raga_names: List[str] = Field(default_factory=list, description="Normalized canonical raga IDs")
    tala_names: List[str] = Field(default_factory=list, description="Original tala names from Saraga JSON")
    normalized_tala_names: List[str] = Field(default_factory=list, description="Normalized canonical tala IDs")
    layas: List[str] = Field(default_factory=list)
    forms: List[str] = Field(default_factory=list)
    artists: List[Dict[str, Any]] = Field(default_factory=list)
    duration_seconds: Optional[float] = None

    # Paths to optional/lazy-loaded annotation files
    pitch_file_path: Optional[str] = None
    sama_file_path: Optional[str] = None
    bpm_file_path: Optional[str] = None
    tempo_file_path: Optional[str] = None
    sections_file_path: Optional[str] = None
    mphrases_file_path: Optional[str] = None
    metadata_json_path: str
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Normalization Utilities
# ============================================================================

def strip_accents(text: str) -> str:
    """Normalize unicode and strip diacritic marks."""
    if not text:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', text)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


def normalize_raga_name(raga_name: Optional[str]) -> str:
    """
    Standardize Saraga raga transliterations to canonical snake_case identifiers.
    
    Examples:
        'Shree' -> 'shree'
        'Bhairabi' -> 'bhairavi'
        'Lalat' -> 'lalit'
        'Miya malhar' / 'Miyan Malhar' -> 'mian_malhar'
        'Aahir Bhairon' / 'Ahir bhairav' -> 'ahir_bhairav'
        'Yaman kalyan' -> 'yaman'
        'Raag Bhimpalasi' -> 'bhimpalasi'
    """
    if not raga_name:
        return ""
    
    clean = strip_accents(raga_name.strip()).lower()
    clean = re.sub(r'^(raag|raga|rag)\s+', '', clean)
    clean = re.sub(r'[\(\)\[\],_\-\/]', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()

    # Canonical mapping table
    RAGA_MAP: Dict[str, str] = {
        "bhairabi": "bhairavi",
        "bhairav": "bhairav",
        "ahir bhairon": "ahir_bhairav",
        "ahir bhairav": "ahir_bhairav",
        "aahir bhairon": "ahir_bhairav",
        "nat bhairon": "nat_bhairav",
        "nat bhairav": "nat_bhairav",
        "lalat": "lalit",
        "lalit": "lalit",
        "lalit pancham": "lalit_pancham",
        "lalitpancham": "lalit_pancham",
        "lalita gauri": "lalita_gauri",
        "miya malhar": "mian_malhar",
        "miyan malhar": "mian_malhar",
        "mian malhar": "mian_malhar",
        "ramdasi malhar": "ramdasi_malhar",
        "ramdasi": "ramdasi_malhar",
        "gaud malhar": "gaud_malhar",
        "gaudmalhar": "gaud_malhar",
        "bhimpalas": "bhimpalasi",
        "bhimpalasi": "bhimpalasi",
        "rageshri": "rageshree",
        "rageshree": "rageshree",
        "raageshree": "rageshree",
        "majh khamaj": "khamaj",
        "maajh khamaj": "khamaj",
        "khamaj": "khamaj",
        "yaman": "yaman",
        "yaman kalyan": "yaman",
        "kalyan": "yaman",
        "sudh kalyan": "shuddha_kalyan",
        "shuddha kalyan": "shuddha_kalyan",
        "jait kalyan": "jait_kalyan",
        "jait": "jait_kalyan",
        "sudh sarang": "shuddha_sarang",
        "shuddh sarang": "shuddha_sarang",
        "shuddha sarang": "shuddha_sarang",
        "bilaskhani todi": "bilaskhani_todi",
        "bilaskhani": "bilaskhani_todi",
        "khat todi": "khat_todi",
        "khat": "khat_todi",
        "todi": "todi",
        "marwa": "marwa",
        "puriya": "puriya",
        "puriya dhanashree": "puriya_dhanashree",
        "pooriya dhanashree": "puriya_dhanashree",
        "shree": "shree",
        "sree": "shree",
        "sri": "shree",
        "bhoopali": "bhoopali",
        "bhupali": "bhoopali",
        "bhoop": "bhoopali",
        "bihag": "bihag",
        "maru bihag": "maru_bihag",
        "marubihag": "maru_bihag",
        "malkauns": "malkauns",
        "malkosh": "malkauns",
        "chandrakauns": "chandrakauns",
        "madhukauns": "madhukauns",
        "madhu kauns": "madhukauns",
        "hameer": "hameer",
        "hamir": "hameer",
        "jog": "jog",
        "jogiya": "jogiya",
        "jogia": "jogiya",
        "kirwani": "kirwani",
        "keeravani": "kirwani",
        "multani": "multani",
        "kedar": "kedar",
        "basanti kedar": "basanti_kedar",
        "basanti": "basanti_kedar",
        "sohani": "sohani",
        "sohini": "sohani",
        "paraj": "paraj",
        "bairagi": "bairagi",
        "bairagi bhairav": "bairagi",
        "saraswati": "saraswati",
        "abhogi": "abhogi",
        "abhogi kanada": "abhogi",
        "megh": "megh",
        "megh malhar": "megh",
        "bahar": "bahar",
        "sawani": "sawani",
        "bibhas": "bibhas",
        "vibhas": "bibhas",
        "bhatiyar": "bhatiyar",
        "dhani": "dhani",
        "gavti": "gavti",
        "gawti": "gawti",
        "desh": "desh",
        "des": "desh",
        "kalavati": "kalavati",
        "kalawati": "kalavati",
        "komal rishav aasavari": "komal_rishabh_asavari",
        "komal rishabh asavari": "komal_rishabh_asavari",
        "asavari": "asavari",
        "shuddha asavari": "asavari",
        "jaunpuri": "jaunpuri",
        "jonpuri": "jaunpuri",
        "dagori deepki": "dagori_deepki",
        "dagori": "dagori_deepki",
        "deepki": "dagori_deepki",
        "hindol pancham": "hindol_pancham",
        "hindol": "hindol_pancham",
        "khokar": "khokar",
        "nat kamod": "nat_kamod",
        "natkamod": "nat_kamod",
        "piloo": "pilu",
        "pilu": "pilu",
        "mishra piloo": "mishra_piloo",
        "mishra pilu": "mishra_piloo",
        "mishra kalingada": "mishra_kalingada",
        "kalingada": "mishra_kalingada",
        "kalingda": "mishra_kalingada",
        "ramgauri gauri": "gauri",
        "gauri": "gauri",
        "sooha kanada": "sooha_kanada",
        "sooha": "sooha_kanada",
        "suha": "sooha_kanada",
        "suha kanada": "sooha_kanada",
        "triveni": "triveni",
        "triveni gauri": "triveni",
        "poorva": "poorva",
        "purvi": "poorva",
        "poorvi": "poorva",
        "lagan gandhar": "lagan_gandhar",
        "lagangandhar": "lagan_gandhar",
        "shankara": "shankara",
        "shankar": "shankara",
        "tilak kamod": "tilak_kamod",
        "tilakkamod": "tilak_kamod",
        "durga": "durga",
        "jaijaiwanti": "jaijaiwanti",
        "jayjaywanti": "jaijaiwanti",
    }

    if clean in RAGA_MAP:
        return RAGA_MAP[clean]
    
    # Fallback to sanitized snake_case
    return clean.replace(' ', '_')


def normalize_tala_name(tala_name: Optional[str]) -> str:
    """
    Standardize Saraga tala transliterations to canonical snake_case identifiers.
    
    Examples:
        'Teentaal' / 'Tīntāl' -> 'teental'
        'Ektaal' / 'Ēktāl' -> 'ektaal'
        'Jhaptaal' -> 'jhaptaal'
        'Tilwada' / 'Tilavāḍā' -> 'tilwada'
        'Rupak' -> 'rupak'
    """
    if not tala_name:
        return ""
    
    clean = strip_accents(tala_name.strip()).lower()
    clean = re.sub(r'^(taal|tala|tal)\s+', '', clean)
    clean = re.sub(r'[\(\)\[\],_\-\/]', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()

    TALA_MAP: Dict[str, str] = {
        "teentaal": "teental",
        "teental": "teental",
        "tintal": "teental",
        "ektaal": "ektaal",
        "ektal": "ektaal",
        "jhaptaal": "jhaptaal",
        "jhaptal": "jhaptaal",
        "tilwada": "tilwada",
        "tilavada": "tilwada",
        "jhoomra": "jhoomra",
        "jhumra": "jhoomra",
        "jatt": "jatt",
        "rupak": "rupak",
        "keherwa": "keherwa",
        "kaharwa": "keherwa",
        "dadra": "dadra",
    }

    if clean in TALA_MAP:
        return TALA_MAP[clean]
    
    return clean.replace(' ', '_')


# ============================================================================
# Abstract Base Adapter
# ============================================================================

class BaseSaragaDatasetAdapter(ABC):
    """Abstract interface for Saraga dataset integration."""

    @abstractmethod
    def scan_dataset(self, dataset_root: Optional[Union[str, Path]] = None) -> List[Path]:
        """Discovers all valid track directories in the dataset."""
        pass

    @abstractmethod
    def get_track_annotations(self, track_dir: Union[str, Path]) -> SaragaTrackAnnotations:
        """Parses track metadata, tonic, and file pointers without loading heavy pitch/audio files."""
        pass

    @abstractmethod
    def load_pitch_contour(self, track: SaragaTrackAnnotations) -> PitchContourData:
        """Lazily reads and parses the continuous F0 pitch contour points."""
        pass

    @abstractmethod
    def load_sama_timestamps(self, track: SaragaTrackAnnotations) -> List[float]:
        """Lazily reads sam timestamps in seconds."""
        pass

    @abstractmethod
    def load_bpm_annotations(self, track: SaragaTrackAnnotations) -> List[BpmAnnotation]:
        """Lazily reads manual BPM annotations."""
        pass

    @abstractmethod
    def load_tempo_annotations(self, track: SaragaTrackAnnotations) -> List[TempoAnnotation]:
        """Lazily reads tempo and meter annotations."""
        pass

    @abstractmethod
    def load_sections(self, track: SaragaTrackAnnotations) -> List[SectionAnnotation]:
        """Lazily reads performance section annotations."""
        pass

    @abstractmethod
    def load_melodic_phrases(self, track: SaragaTrackAnnotations) -> List[MelodicPhraseAnnotation]:
        """Lazily reads melodic phrase / motif annotations."""
        pass

    @abstractmethod
    def iter_tracks(self, dataset_root: Optional[Union[str, Path]] = None) -> Iterator[SaragaTrackAnnotations]:
        """Yields SaragaTrackAnnotations for all discovered tracks in the dataset."""
        pass


# ============================================================================
# Concrete Dataset Adapter Implementation
# ============================================================================

class SaragaDatasetAdapter(BaseSaragaDatasetAdapter):
    """
    Robust, read-only adapter for the Saraga Hindustani 1.5 dataset.
    
    Features:
    - Auto-detects dataset root across common workspace paths.
    - Filters out __MACOSX, hidden files (.DS_Store), and non-track folders.
    - Resolves <Track>.mp3.mp3 audio and all paired annotations.
    - Safely handles tracks with missing or empty metadata.
    - Implements lazy loading for large pitch files (~1.6 GB total) and annotations.
    - Protects against path traversal attacks.
    """

    def __init__(self, dataset_root: Optional[Union[str, Path]] = None):
        if dataset_root:
            self._dataset_root = self.validate_root(dataset_root)
        else:
            self._dataset_root = self.find_dataset_root()

    @property
    def dataset_root(self) -> Path:
        return self._dataset_root

    @classmethod
    def validate_root(cls, path_candidate: Union[str, Path]) -> Path:
        """Validates that candidate directory exists and is within a valid Saraga structure."""
        p = Path(path_candidate).resolve()
        if not p.is_dir():
            raise FileNotFoundError(f"Dataset root directory does not exist: {p}")
        
        # If user passed outer saraga folder containing inner saraga1.5_hindustani, resolve to inner
        nested = p / "saraga1.5_hindustani"
        if nested.is_dir() and (nested / "file_paths.csv").exists():
            return nested
        
        # If folder directly contains file_paths.csv or album directories with .json files
        if (p / "file_paths.csv").exists():
            return p
            
        # Check if subdirectories contain track JSONs
        jsons = list(p.glob("*/*/*.json"))
        if jsons:
            return p

        return p

    @classmethod
    def find_dataset_root(cls, hint_path: Optional[Union[str, Path]] = None) -> Path:
        """
        Auto-discovers the Saraga Hindustani dataset root.
        Searches hint path, environment variable SARAGA_DATASET_ROOT, and workspace defaults.
        """
        candidates: List[Path] = []
        if hint_path:
            candidates.append(Path(hint_path))

        env_root = os.environ.get("SARAGA_DATASET_ROOT")
        if env_root:
            candidates.append(Path(env_root))

        cwd = Path.cwd()
        candidates.extend([
            cwd / "saraga1.5_hindustani" / "saraga1.5_hindustani",
            cwd / "saraga1.5_hindustani",
            cwd / "data" / "datasets" / "saraga1.5_hindustani" / "saraga1.5_hindustani",
            cwd / "data" / "datasets" / "saraga1.5_hindustani",
            cwd.parent / "saraga1.5_hindustani" / "saraga1.5_hindustani",
        ])

        for c in candidates:
            try:
                if c.exists() and c.is_dir():
                    resolved = cls.validate_root(c)
                    if (resolved / "file_paths.csv").exists() or list(resolved.glob("*/*/*.json")):
                        return resolved
            except Exception:
                continue

        raise FileNotFoundError(
            "Could not automatically locate Saraga Hindustani dataset root. "
            "Please specify dataset_root explicitly or set SARAGA_DATASET_ROOT."
        )

    def scan_dataset(self, dataset_root: Optional[Union[str, Path]] = None) -> List[Path]:
        """
        Scans and returns all valid track directories (108 in Saraga Hindustani 1.5).
        Ignores __MACOSX, hidden directories, and non-directory files.
        """
        root = Path(dataset_root).resolve() if dataset_root else self.dataset_root
        if not root.is_dir():
            raise FileNotFoundError(f"Dataset root does not exist: {root}")

        track_dirs: List[Path] = []
        # Traverse top-level album directories
        for item in sorted(root.iterdir()):
            if not item.is_dir():
                continue
            if item.name.startswith(".") or item.name == "__MACOSX":
                continue
            
            # Sub-items within album directory
            for sub in sorted(item.iterdir()):
                if not sub.is_dir():
                    continue
                if sub.name.startswith(".") or sub.name == "__MACOSX":
                    continue
                
                # Check if this leaf folder has a metadata JSON file
                json_files = [f for f in sub.iterdir() if f.is_file() and f.suffix == ".json" and not f.name.startswith(".")]
                if json_files:
                    track_dirs.append(sub)

        return sorted(track_dirs)

    def _assert_path_safe(self, target_path: Path) -> None:
        """Protects against path traversal attacks outside dataset root."""
        try:
            resolved_target = target_path.resolve()
            resolved_root = self.dataset_root.resolve()
            # Allow target to be inside root or within explicit custom track directory
            if not (resolved_target == resolved_root or resolved_target.is_relative_to(resolved_root)):
                # If path is outside dataset root, verify it exists and is a valid directory
                if not resolved_target.exists():
                    raise ValueError(f"Path does not exist or traverses outside dataset root: {target_path}")
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Invalid path traversal attempt: {target_path}") from e

    def get_track_annotations(self, track_dir: Union[str, Path]) -> SaragaTrackAnnotations:
        """
        Parses metadata and annotations for a single track directory.
        Reads JSON metadata and .ctonic.txt; lazily binds paths for pitch, tempo, sama, etc.
        """
        t_dir = Path(track_dir).resolve()
        if not t_dir.exists() or not t_dir.is_dir():
            raise FileNotFoundError(f"Track directory not found: {t_dir}")

        self._assert_path_safe(t_dir)

        # Locate base JSON metadata file
        json_files = [
            f for f in t_dir.iterdir() 
            if f.is_file() and f.suffix == ".json" and not f.name.startswith(".") and not f.name.startswith("._")
        ]
        if not json_files:
            raise ValueError(f"No metadata .json file found in track directory: {t_dir}")

        json_file = json_files[0]
        base_name = json_file.stem

        # Parse JSON
        with open(json_file, "r", encoding="utf-8") as f:
            raw_meta = json.load(f)

        mbid = raw_meta.get("mbid")
        title = raw_meta.get("title", base_name)
        album_name = t_dir.parent.name
        length_ms = raw_meta.get("length")
        duration_seconds = (length_ms / 1000.0) if length_ms else None

        # Extract artists
        artists = raw_meta.get("artists", [])

        # Extract ragas
        raga_names: List[str] = []
        if "raags" in raw_meta and isinstance(raw_meta["raags"], list):
            for r in raw_meta["raags"]:
                if isinstance(r, dict):
                    name = r.get("common_name") or r.get("name")
                    if name:
                        raga_names.append(name)
                elif isinstance(r, str):
                    raga_names.append(r)

        # Extract taals
        tala_names: List[str] = []
        if "taals" in raw_meta and isinstance(raw_meta["taals"], list):
            for t in raw_meta["taals"]:
                if isinstance(t, dict):
                    name = t.get("common_name") or t.get("name")
                    if name:
                        tala_names.append(name)
                elif isinstance(t, str):
                    tala_names.append(t)

        # Fallback heuristic if raags is empty: extract from track title or folder name
        if not raga_names:
            title_raga_match = re.search(r'(?:Raag|Raga|Rag)\s+([A-Za-z\s]+)', title, re.IGNORECASE)
            if title_raga_match:
                extracted_name = title_raga_match.group(1).strip()
                # Split compound titles like 'Abhogi & Megh'
                parts = re.split(r'\s+(?:&|and)\s+', extracted_name)
                for part in parts:
                    if part.strip():
                        raga_names.append(part.strip())

        # Extract layas
        layas: List[str] = []
        if "layas" in raw_meta and isinstance(raw_meta["layas"], list):
            for l in raw_meta["layas"]:
                if isinstance(l, dict):
                    name = l.get("common_name") or l.get("name")
                    if name:
                        layas.append(name)

        # Extract forms
        forms: List[str] = []
        if "forms" in raw_meta and isinstance(raw_meta["forms"], list):
            for form_item in raw_meta["forms"]:
                if isinstance(form_item, dict):
                    name = form_item.get("common_name") or form_item.get("name")
                    if name:
                        forms.append(name)

        # Resolve Audio Path (<BaseName>.mp3.mp3 or <BaseName>.mp3)
        audio_path_double = t_dir / f"{base_name}.mp3.mp3"
        audio_path_single = t_dir / f"{base_name}.mp3"
        if audio_path_double.exists():
            resolved_audio_path = str(audio_path_double)
        elif audio_path_single.exists():
            resolved_audio_path = str(audio_path_single)
        else:
            # Fallback search for any mp3 in directory
            any_mp3 = [f for f in t_dir.glob("*.mp3") if not f.name.startswith(".")]
            resolved_audio_path = str(any_mp3[0]) if any_mp3 else str(audio_path_double)

        # Parse Ground Truth Sa Tonic (ctonic.txt)
        tonic_file = t_dir / f"{base_name}.ctonic.txt"
        tonic_hz: Optional[float] = None
        if tonic_file.exists():
            try:
                with open(tonic_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        tonic_hz = float(content)
            except Exception as e:
                logger.warning(f"Error parsing ctonic file {tonic_file}: {e}")

        # Resolve annotation file paths
        pitch_file = t_dir / f"{base_name}.pitch.txt"
        sama_file = t_dir / f"{base_name}.sama-manual.txt"
        bpm_file = t_dir / f"{base_name}.bpm-manual.txt"
        tempo_file = t_dir / f"{base_name}.tempo-manual.txt"
        sections_file = t_dir / f"{base_name}.sections-manual-p.txt"
        mphrases_file = t_dir / f"{base_name}.mphrases-manual.txt"

        normalized_ragas = [normalize_raga_name(r) for r in raga_names if normalize_raga_name(r)]
        normalized_talas = [normalize_tala_name(t) for t in tala_names if normalize_tala_name(t)]

        sample_id = mbid or f"{album_name}/{title}"

        return SaragaTrackAnnotations(
            sample_id=sample_id,
            album_name=album_name,
            track_title=title,
            audio_path=resolved_audio_path,
            mbid=mbid,
            tonic_hz=tonic_hz,
            raga_names=raga_names,
            normalized_raga_names=normalized_ragas,
            tala_names=tala_names,
            normalized_tala_names=normalized_talas,
            layas=layas,
            forms=forms,
            artists=artists,
            duration_seconds=duration_seconds,
            pitch_file_path=str(pitch_file) if pitch_file.exists() else None,
            sama_file_path=str(sama_file) if sama_file.exists() else None,
            bpm_file_path=str(bpm_file) if bpm_file.exists() else None,
            tempo_file_path=str(tempo_file) if tempo_file.exists() else None,
            sections_file_path=str(sections_file) if sections_file.exists() else None,
            mphrases_file_path=str(mphrases_file) if mphrases_file.exists() else None,
            metadata_json_path=str(json_file),
            raw_metadata=raw_meta,
        )

    def load_pitch_contour(self, track: SaragaTrackAnnotations) -> PitchContourData:
        """
        Lazily reads and parses the continuous F0 pitch contour points (~225 Hz)
        from `<Track>.pitch.txt`.
        """
        if not track.pitch_file_path or not Path(track.pitch_file_path).exists():
            return PitchContourData(time_stamps=[], frequencies_hz=[])

        self._assert_path_safe(Path(track.pitch_file_path))

        timestamps: List[float] = []
        frequencies: List[float] = []

        with open(track.pitch_file_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                parts = line_str.split("\t")
                if len(parts) >= 2:
                    try:
                        t = float(parts[0])
                        f0 = float(parts[1])
                        timestamps.append(t)
                        frequencies.append(f0)
                    except ValueError:
                        continue

        return PitchContourData(time_stamps=timestamps, frequencies_hz=frequencies)

    def load_sama_timestamps(self, track: SaragaTrackAnnotations) -> List[float]:
        """
        Lazily reads sam timestamps (in seconds) from `<Track>.sama-manual.txt`.
        """
        if not track.sama_file_path or not Path(track.sama_file_path).exists():
            return []

        self._assert_path_safe(Path(track.sama_file_path))

        samas: List[float] = []
        with open(track.sama_file_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    try:
                        samas.append(float(line_str))
                    except ValueError:
                        continue
        return samas

    def load_bpm_annotations(self, track: SaragaTrackAnnotations) -> List[BpmAnnotation]:
        """
        Lazily reads BPM annotations from `<Track>.bpm-manual.txt`.
        Format: `bpm, start_s, end_s`
        """
        if not track.bpm_file_path or not Path(track.bpm_file_path).exists():
            return []

        self._assert_path_safe(Path(track.bpm_file_path))

        annotations: List[BpmAnnotation] = []
        with open(track.bpm_file_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                parts = [p.strip() for p in line_str.split(",")]
                if len(parts) >= 3:
                    try:
                        bpm_val = float(parts[0]) if parts[0] != "-" else 0.0
                        start_s = float(parts[1])
                        end_s = float(parts[2])
                        annotations.append(BpmAnnotation(bpm=bpm_val, start_s=start_s, end_s=end_s))
                    except ValueError:
                        continue
        return annotations

    def load_tempo_annotations(self, track: SaragaTrackAnnotations) -> List[TempoAnnotation]:
        """
        Lazily reads tempo and meter annotations from `<Track>.tempo-manual.txt`.
        Format: `bpm, beat_duration_s, matra_duration_s, matras, start_s, end_s`
        """
        if not track.tempo_file_path or not Path(track.tempo_file_path).exists():
            return []

        self._assert_path_safe(Path(track.tempo_file_path))

        annotations: List[TempoAnnotation] = []
        with open(track.tempo_file_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                parts = [p.strip() for p in line_str.split(",")]
                if len(parts) >= 6:
                    try:
                        bpm = float(parts[0])
                        beat_dur = float(parts[1])
                        matra_dur = float(parts[2])
                        matras = int(float(parts[3]))
                        start_s = float(parts[4])
                        end_s = float(parts[5])
                        annotations.append(TempoAnnotation(
                            bpm=bpm,
                            beat_duration_s=beat_dur,
                            matra_duration_s=matra_dur,
                            matras_per_cycle=matras,
                            start_s=start_s,
                            end_s=end_s,
                        ))
                    except ValueError:
                        continue
        return annotations

    def load_sections(self, track: SaragaTrackAnnotations) -> List[SectionAnnotation]:
        """
        Lazily reads performance section annotations from `<Track>.sections-manual-p.txt`.
        Format: `start_s, section_idx, duration_s, section_label`
        """
        if not track.sections_file_path or not Path(track.sections_file_path).exists():
            return []

        self._assert_path_safe(Path(track.sections_file_path))

        sections: List[SectionAnnotation] = []
        with open(track.sections_file_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                parts = [p.strip() for p in line_str.split(",")]
                if len(parts) >= 4:
                    try:
                        start_s = float(parts[0])
                        idx = int(parts[1])
                        dur_s = float(parts[2])
                        label = ",".join(parts[3:]).strip()
                        sections.append(SectionAnnotation(
                            start_s=start_s,
                            section_index=idx,
                            duration_s=dur_s,
                            label=label,
                        ))
                    except ValueError:
                        continue
        return sections

    def load_melodic_phrases(self, track: SaragaTrackAnnotations) -> List[MelodicPhraseAnnotation]:
        """
        Lazily reads melodic phrase annotations from `<Track>.mphrases-manual.txt`.
        Format: `onset_s \t voiced_flag \t duration_s \t swara_str`
        """
        if not track.mphrases_file_path or not Path(track.mphrases_file_path).exists():
            return []

        self._assert_path_safe(Path(track.mphrases_file_path))

        phrases: List[MelodicPhraseAnnotation] = []
        with open(track.mphrases_file_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                parts = line_str.split("\t")
                if len(parts) >= 4:
                    try:
                        onset = float(parts[0])
                        voiced = int(parts[1])
                        dur = float(parts[2])
                        swaras = parts[3].strip()
                        phrases.append(MelodicPhraseAnnotation(
                            onset_s=onset,
                            voiced_flag=voiced,
                            duration_s=dur,
                            phrase_swaras=swaras,
                        ))
                    except ValueError:
                        continue
        return phrases

    def iter_tracks(self, dataset_root: Optional[Union[str, Path]] = None) -> Iterator[SaragaTrackAnnotations]:
        """Iterates through all validated tracks in the dataset without high memory overhead."""
        for t_dir in self.scan_dataset(dataset_root):
            try:
                yield self.get_track_annotations(t_dir)
            except Exception as e:
                logger.error(f"Error loading track {t_dir}: {e}")
                continue
