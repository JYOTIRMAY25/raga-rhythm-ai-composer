import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import AnalysisResult from "./AnalysisResult";
import { AnalysisResponse } from "@/types/api";
import { api } from "@/services/api";

describe("AnalysisResult Component", () => {
  beforeEach(() => {
    vi.spyOn(api, "explainAnalysis").mockResolvedValue({
      available: true,
      summary: "Test summary",
      tonic_explanation: "Test tonic",
      raga_explanation: "Test raga",
      swara_explanation: "Test swara",
      tala_explanation: "Test tala",
      educational_notes: ["Note 1"],
      model_used: "gemini-2.5-flash",
    });
  });
  const mockAnalysis: AnalysisResponse = {
    audio_metadata: {
      filename: "saraga_test_track.wav",
      duration_seconds: 45.2,
      sample_rate: 44100,
      channels: 1,
      format: "wav",
    },
    tonic: {
      note_name: "C#",
      frequency_hz: 138.59,
      confidence: 0.95,
      is_ambiguous: false,
    },
    pitch: {
      voiced_frames: 4200,
      unvoiced_frames: 320,
      voiced_percentage: 92.9,
      mean_f0_hz: 195.4,
      median_f0_hz: 190.2,
      min_f0_hz: 110.0,
      max_f0_hz: 380.0,
      pitch_confidence_mean: 0.91,
      downsampled_timestamps: [0.0, 0.5, 1.0, 1.5, 2.0],
      downsampled_frequencies: [138.5, 142.0, 155.0, 160.0, 138.5],
    },
    swara: {
      dominant_swaras: ["S", "r", "G", "m", "P", "d", "N"],
      swara_coverage: 0.92,
      pitch_class_distribution: {
        S: 0.28,
        r: 0.18,
        G: 0.15,
        m: 0.12,
        P: 0.14,
        d: 0.08,
        N: 0.05,
      },
      transitions_top: [
        { from: "S", to: "r", count: 12 },
        { from: "r", to: "G", count: 8 },
      ],
    },
    raga: {
      name: "Bhairav",
      confidence: 0.88,
      thaat: "Bhairav",
      time: "Morning",
      mood: "Devotion, Peace",
      vadi: "d",
      samvadi: "r",
      aroha: ["S", "r", "G", "m", "P", "d", "N", "S'"],
      avaroha: ["S'", "N", "d", "P", "m", "G", "r", "S"],
      is_ambiguous: false,
      alternatives: [
        { name: "Ahir Bhairav", confidence: 0.62, thaat: "Bhairav" },
      ],
      motif_matches: [
        { motif_str: "G - m - d - P", similarity_score: 0.91, match_type: "exact" },
      ],
    },
    rhythm: {
      estimated_bpm: 84.0,
      tempo_confidence: 0.82,
      laya: "Madhya",
      is_regular: true,
      beat_count: 64,
    },
    tala: {
      name: "Teental",
      matras: 16,
      vibhag_structure: "4+4+4+4",
      confidence: 0.86,
      sam_position: 1,
      theka: ["Dha", "Dhin", "Dhin", "Dha", "Dha", "Dhin", "Dhin", "Dha"],
      tali_positions: [1, 5, 13],
      khali_positions: [9],
      is_ambiguous: false,
    },
    warnings: [
      { stage: "Tonic Resolver", message: "Harmonic peak detected at 277.2 Hz." },
    ],
    processing_time_ms: 1240,
  };

  it("renders raga name, metadata, and confidence badge", () => {
    render(<AnalysisResult analysis={mockAnalysis} />);

    expect(screen.getByText("Bhairav")).toBeInTheDocument();
    expect(screen.getByText("88% Raga Confidence")).toBeInTheDocument();
    expect(screen.getByText(/Track: saraga_test_track\.wav/i)).toBeInTheDocument();
  });

  it("renders tonic and rhythm details correctly", () => {
    render(<AnalysisResult analysis={mockAnalysis} />);

    expect(screen.getByText(/C#\s*\(138\.6\s*Hz\)/i)).toBeInTheDocument();
    expect(screen.getByText(/84 BPM/i)).toBeInTheDocument();
    expect(screen.getByText(/Teental\s*\(16 beats\)/i)).toBeInTheDocument();
  });

  it("renders aroha and avaroha lines", () => {
    render(<AnalysisResult analysis={mockAnalysis} />);

    expect(screen.getByText(/Aroha \(Ascent\):/i)).toBeInTheDocument();
    expect(screen.getByText(/Avaroha \(Descent\):/i)).toBeInTheDocument();
  });

  it("renders diagnostic warnings from backend", () => {
    render(<AnalysisResult analysis={mockAnalysis} />);

    expect(screen.getByText(/Diagnostic Notices/i)).toBeInTheDocument();
    expect(screen.getByText(/Harmonic peak detected at 277.2 Hz./i)).toBeInTheDocument();
  });
});
