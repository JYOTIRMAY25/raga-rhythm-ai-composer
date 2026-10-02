"""
Deterministic, theory-constrained melodic phrase generator for Indian Classical Music.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple
from backend.app.composition.raga_constraints import RagaConstraints, normalize_swara_symbol
from backend.app.composition.tala_constraints import TalaConstraints


class MelodyGenerator:
    """Generates structured classical melodic movements adhering to Raga and Tala rules."""

    def __init__(
        self,
        raga_constraints: RagaConstraints,
        tala_constraints: TalaConstraints,
        creativity_score: int = 50,
        seed: Optional[int] = None,
    ):
        self.raga = raga_constraints
        self.tala = tala_constraints
        self.creativity = max(0, min(100, creativity_score))
        self.seed = seed if seed is not None else random.randint(100000, 999999)
        self.rng = random.Random(self.seed)

    def generate_composition_melody(
        self, total_cycles: int, style: str = "bandish"
    ) -> List[List[Dict[str, Any]]]:
        """
        Generates a multi-cycle structured melodic progression:
        - Cycles 1 to 2: Sthayi (lower and middle octave exploration, Vadi emphasis)
        - Cycle 3 to N-1: Antara (expansion into Tara Saptak)
        - Final Cycle: Tihai cadence resolving on Sam
        """
        cycles_data: List[List[Dict[str, Any]]] = []

        for cycle_idx in range(1, total_cycles + 1):
            if total_cycles == 1:
                # Single cycle: Sthayi with closing Sam resolution
                cycle_events = self._generate_sthayi_cycle(cycle_idx, is_final=(cycle_idx == total_cycles))
            elif cycle_idx <= max(1, total_cycles // 2):
                # Sthayi section
                cycle_events = self._generate_sthayi_cycle(cycle_idx, is_final=False)
            elif cycle_idx < total_cycles:
                # Antara section
                cycle_events = self._generate_antara_cycle(cycle_idx)
            else:
                # Concluding Tihai / Sam resolution cycle
                cycle_events = self._generate_tihai_cycle(cycle_idx)

            cycles_data.append(cycle_events)

        return cycles_data

    def _generate_sthayi_cycle(self, cycle_number: int, is_final: bool = False) -> List[Dict[str, Any]]:
        """Generates Sthayi movement focused on Purvanga, Vadi, and Sam."""
        matras = self.tala.matras
        events = []
        current_matra = 1

        # Determine scale pool for Sthayi (Mandra N., S, R, G, m/M, P, D)
        pool = self.raga.aroha_swaras + self.raga.avaroha_swaras
        # Filter mostly to Madhya and upper Mandra
        valid_pool = list(dict.fromkeys(pool))

        # Include pakad motif if available
        pakad_symbols = [normalize_swara_symbol(p)[0] for p in self.raga.pakad if p]

        while current_matra <= matras:
            beat_info = self.tala.get_beat_info(current_matra)

            # Choose swara: Sam gets Sa or Vadi
            if beat_info["is_sam"]:
                swara_choice = "S" if (cycle_number == 1 or not self.raga.vadi) else self.raga.vadi
                octave_choice = 0
                ornament = "straight"
                duration = 1.0 if self.rng.random() > 0.4 else 2.0
            elif pakad_symbols and current_matra in (3, 5, 7) and self.rng.random() < 0.6:
                idx = (current_matra) % len(pakad_symbols)
                swara_choice = pakad_symbols[idx]
                octave_choice = 0
                ornament = "meend" if self.rng.random() < 0.5 else "straight"
                duration = 1.0
            elif beat_info["is_khali"]:
                # Khali often touches Samvadi or Madhyam
                swara_choice = self.raga.samvadi if self.raga.samvadi in valid_pool else valid_pool[0]
                octave_choice = 0
                ornament = "andolan" if self.rng.random() < 0.4 else "straight"
                duration = 1.0
            else:
                swara_choice = self.rng.choice(valid_pool) if valid_pool else "S"
                octave_choice = -1 if (swara_choice in ("N", "n", "D", "d") and self.rng.random() < 0.3) else 0
                ornament = "meend" if (self.rng.random() < (self.creativity / 200.0)) else "straight"
                duration = 1.0

            # Prevent duration overflowing cycle
            remaining = matras - current_matra + 1
            duration = min(duration, float(remaining))

            full_symbol = f"{swara_choice}." if octave_choice == -1 else (f"{swara_choice}'" if octave_choice == 1 else swara_choice)
            pitch_hz = self.raga.swara_to_hz(full_symbol)

            events.append({
                "cycle": cycle_number,
                "vibhag": beat_info["vibhag"],
                "matra": current_matra,
                "subdivision": 0,
                "swara": full_symbol,
                "octave": octave_choice,
                "pitch_hz": pitch_hz,
                "duration_matras": duration,
                "theka_bol": beat_info["bol"],
                "ornament": ornament,
                "is_vadi": (swara_choice == self.raga.vadi),
                "is_samvadi": (swara_choice == self.raga.samvadi),
                "is_sam_landing": beat_info["is_sam"],
            })

            current_matra += int(duration)

        return events

    def _generate_antara_cycle(self, cycle_number: int) -> List[Dict[str, Any]]:
        """Generates Antara movement ascending to Uttaranga and Tara Saptak (high Sa)."""
        matras = self.tala.matras
        events = []
        current_matra = 1

        # Pool geared towards higher registers: P, D, N, S', R', G'
        upper_swaras = [s for s in (self.raga.aroha_swaras + self.raga.avaroha_swaras) if s in ("P", "d", "D", "n", "N", "S")]
        if not upper_swaras:
            upper_swaras = self.raga.aroha_swaras or ["S", "P", "S'"]

        while current_matra <= matras:
            beat_info = self.tala.get_beat_info(current_matra)

            if beat_info["is_sam"]:
                # Landing on Sam in Antara often hits Tara Sa (S') or Pa
                swara_choice = "S"
                octave_choice = 1  # Tara Sa
                ornament = "straight"
                duration = 1.0
            elif current_matra >= (matras // 2):
                # Peak of Antara: High Re/Ga or Tara Sa
                swara_choice = self.rng.choice(self.raga.aroha_swaras[:3]) if self.raga.aroha_swaras else "S"
                octave_choice = 1 if swara_choice in ("S", "r", "R", "g", "G") else 0
                ornament = "gamak" if self.rng.random() < 0.3 else "meend"
                duration = 1.0
            else:
                swara_choice = self.rng.choice(upper_swaras)
                octave_choice = 0
                ornament = "straight"
                duration = 1.0

            remaining = matras - current_matra + 1
            duration = min(duration, float(remaining))

            full_symbol = f"{swara_choice}." if octave_choice == -1 else (f"{swara_choice}'" if octave_choice == 1 else swara_choice)
            pitch_hz = self.raga.swara_to_hz(full_symbol)

            events.append({
                "cycle": cycle_number,
                "vibhag": beat_info["vibhag"],
                "matra": current_matra,
                "subdivision": 0,
                "swara": full_symbol,
                "octave": octave_choice,
                "pitch_hz": pitch_hz,
                "duration_matras": duration,
                "theka_bol": beat_info["bol"],
                "ornament": ornament,
                "is_vadi": (swara_choice == self.raga.vadi),
                "is_samvadi": (swara_choice == self.raga.samvadi),
                "is_sam_landing": beat_info["is_sam"],
            })

            current_matra += int(duration)

        return events

    def _generate_tihai_cycle(self, cycle_number: int) -> List[Dict[str, Any]]:
        """
        Generates a cadential Tihai (3-fold repetitive phrase) that resolves with
        mathematical precision on Sam (beat 1).
        """
        matras = self.tala.matras
        events = []

        # Construct a 3-note cadential phrase: e.g. G - M - P or R - G - S
        phrase_base = self.raga.avaroha_swaras[-3:] if len(self.raga.avaroha_swaras) >= 3 else ["R", "N.", "S"]
        p1, p2, p3 = phrase_base[0], phrase_base[1], "S"

        # Repeat phrase 3 times across the final cycle
        step_len = max(1, matras // 4)
        tihai_sequence = [
            (p1, 0, 1.0), (p2, 0, 1.0), (p3, 0, 1.0),
            (p1, 0, 1.0), (p2, 0, 1.0), (p3, 0, 1.0),
            (p1, 0, 1.0), (p2, 0, 1.0), ("S", 0, 2.0),
        ]

        current_matra = 1
        seq_idx = 0

        while current_matra <= matras:
            beat_info = self.tala.get_beat_info(current_matra)

            if seq_idx < len(tihai_sequence):
                swara_choice, octave_choice, duration = tihai_sequence[seq_idx]
                seq_idx += 1
            else:
                swara_choice, octave_choice, duration = "S", 0, 1.0

            remaining = matras - current_matra + 1
            duration = min(duration, float(remaining))

            full_symbol = f"{swara_choice}." if octave_choice == -1 else (f"{swara_choice}'" if octave_choice == 1 else swara_choice)
            pitch_hz = self.raga.swara_to_hz(full_symbol)

            events.append({
                "cycle": cycle_number,
                "vibhag": beat_info["vibhag"],
                "matra": current_matra,
                "subdivision": 0,
                "swara": full_symbol,
                "octave": octave_choice,
                "pitch_hz": pitch_hz,
                "duration_matras": duration,
                "theka_bol": beat_info["bol"],
                "ornament": "straight" if current_matra == 1 else "meend",
                "is_vadi": (swara_choice == self.raga.vadi),
                "is_samvadi": (swara_choice == self.raga.samvadi),
                "is_sam_landing": beat_info["is_sam"] or (current_matra == 1),
            })

            current_matra += int(duration)

        return events
