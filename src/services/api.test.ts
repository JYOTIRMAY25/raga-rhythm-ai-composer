import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api, ApiError } from "./api";
import { AnalysisResponse, HealthResponse, NotImplementedResponse, Raga, Tala } from "@/types/api";

describe("API Client Service (src/services/api.ts)", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  // 1. API client health request
  it("getHealth() returns healthy status response", async () => {
    const mockHealth: HealthResponse = {
      status: "healthy",
      version: "1.0.0",
      service: "raga-rhythm-ai-analysis",
      timestamp: "2026-10-01T12:00:00Z",
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockHealth,
    });

    const result = await api.getHealth();
    expect(result.status).toBe("healthy");
    expect(result.service).toBe("raga-rhythm-ai-analysis");
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining("/health"));
  });

  // 2. Successful audio analysis
  it("analyzeAudio(file) performs multipart POST and returns AnalysisResponse", async () => {
    const mockAnalysis: AnalysisResponse = {
      success: true,
      audio_metadata: {
        filename: "test_alaap.wav",
        duration_seconds: 15.2,
        sample_rate: 44100,
        channels: 1,
        format: "wav",
      },
      tonic: {
        detected_tonic: "D#",
        frequency_hz: 155.56,
        confidence: 0.94,
        source: "resolver",
      },
      pitch: {
        voiced_frames: 1200,
        unvoiced_frames: 300,
        voicing_ratio: 0.8,
        mean_pitch_hz: 220.0,
        median_pitch_hz: 215.0,
        min_pitch_hz: 130.0,
        max_pitch_hz: 450.0,
        pitch_contour_sample: [155.5, 158.0, 162.0],
      },
      swara: {
        dominant_swaras: ["S", "R1", "G2", "M1", "P", "D1", "N2"],
        swara_coverage: 0.88,
        register_distribution: { mandra: 0.2, madhya: 0.6, tara: 0.2 },
        pitch_class_distribution: { S: 0.25, R1: 0.15, G2: 0.2, M1: 0.1, P: 0.18, D1: 0.08, N2: 0.04 },
        transitions: [["S", "R1"], ["R1", "G2"], ["G2", "M1"]],
      },
      raga: {
        primary_raga: {
          id: "bhairav",
          name: "Bhairav",
          confidence: 0.89,
          evidence: { swara_match: 0.92, vadi_match: 1.0 },
        },
        candidates: [
          { raga_id: "bhairav", name: "Bhairav", confidence: 0.89 },
          { raga_id: "ahir_bhairav", name: "Ahir Bhairav", confidence: 0.72 },
        ],
        motifs_detected: [
          { pattern: ["G2", "M1", "R1", "S"], confidence: 0.85, name: "Bhairav Andolan" },
        ],
        ambiguity_warning: null,
      },
      rhythm: {
        bpm: 72.0,
        confidence: 0.88,
        is_rhythmic: true,
        beat_grid: {
          beat_count: 32,
          sam_estimate_seconds: 0.85,
        },
      },
      tala: {
        primary_tala: {
          id: "teental",
          name: "Teental",
          matras: 16,
          confidence: 0.82,
        },
        candidates: [{ tala_id: "teental", name: "Teental", confidence: 0.82 }],
      },
      warnings: [],
      execution_time_seconds: 1.45,
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockAnalysis,
    });

    const dummyFile = new File(["fake_audio_bytes"], "test_alaap.wav", { type: "audio/wav" });
    const result = await api.analyzeAudio(dummyFile);

    expect(result.success).toBe(true);
    expect(result.raga.primary_raga?.name).toBe("Bhairav");
    expect(result.tonic.detected_tonic).toBe("D#");
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/analyze"),
      expect.objectContaining({ method: "POST" })
    );
  });

  // 5. Backend 400 handling
  it("analyzeAudio handles backend 400 error cleanly", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: "Bad Request",
      json: async () => ({
        error_code: "INVALID_AUDIO_PAYLOAD",
        message: "Audio file is corrupt or unsupported.",
        status_code: 400,
      }),
    });

    const dummyFile = new File([""], "empty.wav", { type: "audio/wav" });
    await expect(api.analyzeAudio(dummyFile)).rejects.toThrow(ApiError);

    try {
      await api.analyzeAudio(dummyFile);
    } catch (e) {
      const err = e as ApiError;
      expect(err.statusCode).toBe(400);
      expect(err.errorCode).toBe("INVALID_AUDIO_PAYLOAD");
      expect(err.message).toBe("Audio file is corrupt or unsupported.");
    }
  });

  // 6. Backend 413 handling
  it("analyzeAudio handles backend 413 file too large", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 413,
      statusText: "Payload Too Large",
      json: async () => ({
        error_code: "FILE_TOO_LARGE",
        message: "Audio file size exceeds the 25 MB limit.",
        status_code: 413,
      }),
    });

    const dummyFile = new File(["huge".repeat(100)], "huge.wav", { type: "audio/wav" });
    try {
      await api.analyzeAudio(dummyFile);
    } catch (e) {
      const err = e as ApiError;
      expect(err.statusCode).toBe(413);
      expect(err.errorCode).toBe("FILE_TOO_LARGE");
    }
  });

  // 7. Backend 500 handling
  it("analyzeAudio handles backend 500 error", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: async () => ({
        error_code: "INTERNAL_PROCESSING_ERROR",
        message: "An unexpected error occurred in analysis pipeline.",
        status_code: 500,
      }),
    });

    const dummyFile = new File(["data"], "test.wav", { type: "audio/wav" });
    await expect(api.analyzeAudio(dummyFile)).rejects.toThrow("An unexpected error occurred in analysis pipeline.");
  });

  // 8. Network failure handling
  it("analyzeAudio throws on network/fetch failure", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Failed to fetch"));

    const dummyFile = new File(["data"], "test.wav", { type: "audio/wav" });
    await expect(api.analyzeAudio(dummyFile)).rejects.toThrow("Failed to fetch");
  });

  // 11. Raga catalog loading
  it("getRagas() returns raga catalog list", async () => {
    const mockRagas: Raga[] = [
      {
        id: "yaman",
        name: "Yaman",
        thaat: "Kalyan",
        time: "Evening",
        aroha: ["N.", "R", "G", "M'", "D", "N", "S'"],
        avaroha: ["S'", "N", "D", "P", "M'", "G", "R", "S"],
        vadi: "G",
        samvadi: "N",
        pakad: ["N.", "R", "G", "M'", "P", "R", "G", "R", "S"],
        description: "A serene evening raga.",
      },
    ];

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ragas: mockRagas, total: 1 }),
    });

    const result = await api.getRagas();
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("Yaman");
  });

  // 12. Raga search query
  it("getRagas({ search: 'Bhairav' }) includes query param", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ragas: [], total: 0 }),
    });

    await api.getRagas({ search: "Bhairav", thaat: "Bhairav" });
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("search=Bhairav")
    );
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("thaat=Bhairav")
    );
  });

  // 13. Tala catalog loading
  it("getTalas() returns tala catalog list", async () => {
    const mockTalas: Tala[] = [
      {
        id: "teental",
        name: "Teental",
        matras: 16,
        vibhag_structure: [4, 4, 4, 4],
        theka: ["Dha", "Dhin", "Dhin", "Dha", "Dha", "Dhin", "Dhin", "Dha", "Dha", "Tin", "Tin", "Ta", "Ta", "Dhin", "Dhin", "Dha"],
        tali: [1, 5, 13],
        khali: [9],
        description: "The primary 16-beat cycle of Hindustani music.",
      },
    ];

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ talas: mockTalas, total: 1 }),
    });

    const result = await api.getTalas();
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("Teental");
    expect(result[0].matras).toBe(16);
  });

  // 14. Composition generation
  it("generateComposition() returns CompositionResponse with symbolic score and cycles", async () => {
    const mockCompositionResponse = {
      success: true,
      raga_id: "yaman",
      raga_name: "Yaman",
      tala_id: "teental",
      tala_name: "Teental",
      tonic_hz: 220.0,
      tempo_bpm: 80,
      seed: 42,
      composition: {
        raga_id: "yaman",
        tala_id: "teental",
        tonic_hz: 220.0,
        tempo_bpm: 80,
        matras_per_cycle: 16,
        cycles: [
          {
            cycle_index: 0,
            section: "sthayi",
            vibhag_boundaries: [0, 4, 8, 12],
            events: [
              { swara: "N.", octave: -1, matra_offset: 0, duration_matras: 1.0, pitch_hz: 207.65, is_sam: true, theka_bol: "Dha" }
            ]
          }
        ],
        total_matras: 16,
        duration_seconds: 12.0
      },
      validation: {
        is_valid: true,
        forbidden_swara_violations: [],
        register_violations: [],
        matra_violations: [],
        pitch_sanity_passed: true,
        sam_aligned: true,
        diagnostics: []
      },
      disclaimer: "Algorithmically generated representation based on raga grammar rules."
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockCompositionResponse,
    });

    const result = await api.generateComposition({
      raga_id: "yaman",
      tala_id: "teental",
      tempo_bpm: 80,
    });

    expect(result.success).toBe(true);
    expect(result.raga_name).toBe("Yaman");
    expect(result.composition.cycles).toHaveLength(1);
    expect(result.validation.is_valid).toBe(true);
  });

  // 15. AI Explanation
  it("explainAnalysis() returns GeminiAnalysisExplanation", async () => {
    const mockExplanation = {
      available: true,
      summary: "This performance is in Raga Bhairav set to Teental.",
      tonic_explanation: "Tonic detected at D# (155.56 Hz).",
      raga_explanation: "Bhairav features Komal Rishabh (r) and Komal Dhaivat (d).",
      swara_distribution_explanation: "Strong emphasis on Sa and Pa.",
      tala_rhythm_explanation: "16-beat Teental with sam at 0.85s.",
      educational_notes: ["Bhairav is traditionally performed at dawn."],
      model_used: "gemini-2.5-flash"
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockExplanation,
    });

    const result = await api.explainAnalysis({
      detected_raga: "Bhairav",
      detected_tala: "Teental",
      tonic_note: "D#",
      tonic_hz: 155.56,
      bpm: 72.0,
      dominant_swaras: ["S", "r", "G", "m", "P", "d", "N"],
    });

    expect(result.available).toBe(true);
    expect(result.summary).toContain("Raga Bhairav");
    expect(result.model_used).toBe("gemini-2.5-flash");
  });
});
