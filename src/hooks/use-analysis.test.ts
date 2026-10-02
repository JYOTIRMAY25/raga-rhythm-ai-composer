import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useAnalysis } from "./use-analysis";
import { api, ApiError } from "@/services/api";
import { AnalysisResponse } from "@/types/api";

vi.mock("@/services/api", () => ({
  api: {
    analyzeAudio: vi.fn(),
  },
  ApiError: class extends Error {
    public statusCode: number;
    public errorCode: string;
    public details?: Record<string, unknown> | null;
    constructor(detail: { message: string; status_code: number; error_code: string; details?: Record<string, unknown> | null }) {
      super(detail.message);
      this.statusCode = detail.status_code;
      this.errorCode = detail.error_code;
      this.details = detail.details;
    }
  },
}));

vi.mock("@/components/ui/use-toast", () => ({
  toast: vi.fn(),
}));

describe("useAnalysis Hook (src/hooks/use-analysis.ts)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("initializes in idle state with null result and null errors", () => {
    const { result } = renderHook(() => useAnalysis());

    expect(result.current.status).toBe("idle");
    expect(result.current.audioFile).toBeNull();
    expect(result.current.analysisResult).toBeNull();
    expect(result.current.isAnalyzing).toBe(false);
    expect(result.current.errorMessage).toBeNull();
  });

  it("handles valid file selection transitioning to selected state", () => {
    const { result } = renderHook(() => useAnalysis());
    const validFile = new File(["audio-content"], "alaap.wav", { type: "audio/wav" });

    act(() => {
      result.current.handleFileChange(validFile);
    });

    expect(result.current.status).toBe("selected");
    expect(result.current.audioFile).toBe(validFile);
    expect(result.current.errorMessage).toBeNull();
  });

  it("validates and rejects empty files (0 bytes)", () => {
    const { result } = renderHook(() => useAnalysis());
    const emptyFile = new File([], "empty.wav", { type: "audio/wav" });

    act(() => {
      result.current.handleFileChange(emptyFile);
    });

    expect(result.current.status).toBe("error");
    expect(result.current.errorMessage).toContain("empty");
  });

  it("validates and rejects unsupported extensions", () => {
    const { result } = renderHook(() => useAnalysis());
    const textFile = new File(["some text"], "notes.txt", { type: "text/plain" });

    act(() => {
      result.current.handleFileChange(textFile);
    });

    expect(result.current.status).toBe("error");
    expect(result.current.errorMessage).toContain("Unsupported file format");
  });

  it("successfully performs audio analysis and sets analysisResult", async () => {
    const mockResponse: AnalysisResponse = {
      success: true,
      audio_metadata: {
        filename: "yaman.wav",
        duration_seconds: 12.0,
        sample_rate: 44100,
        channels: 1,
        format: "wav",
      },
      tonic: { detected_tonic: "C", frequency_hz: 130.81, confidence: 0.95 },
      pitch: {
        voiced_frames: 800,
        unvoiced_frames: 200,
        voicing_ratio: 0.8,
        mean_pitch_hz: 180,
        median_pitch_hz: 175,
        min_pitch_hz: 120,
        max_pitch_hz: 360,
      },
      swara: {
        dominant_swaras: ["S", "R", "G", "M'", "P", "D", "N"],
        swara_coverage: 0.9,
        register_distribution: {},
        pitch_class_distribution: { S: 0.2, G: 0.3, P: 0.25 },
        transitions: [],
      },
      raga: {
        name: "Yaman",
        confidence: 0.92,
        primary_raga: { id: "yaman", name: "Yaman", confidence: 0.92 },
        candidates: [{ raga_id: "yaman", name: "Yaman", confidence: 0.92 }],
        motifs_detected: [],
      },
      rhythm: {
        bpm: 80.0,
        confidence: 0.85,
        is_rhythmic: true,
      },
      tala: {
        name: "Teental",
        matras: 16,
        confidence: 0.88,
      },
      warnings: [],
      execution_time_seconds: 0.98,
    };

    vi.mocked(api.analyzeAudio).mockResolvedValueOnce(mockResponse);

    const { result } = renderHook(() => useAnalysis());
    const validFile = new File(["valid-audio-data"], "yaman.wav", { type: "audio/wav" });

    act(() => {
      result.current.handleFileChange(validFile);
    });

    await act(async () => {
      await result.current.analyzeAudio();
    });

    expect(result.current.status).toBe("success");
    expect(result.current.isAnalyzing).toBe(false);
    expect(result.current.analysisResult).toEqual(mockResponse);
  });

  it("handles analysis API error gracefully and sets error message", async () => {
    vi.mocked(api.analyzeAudio).mockRejectedValueOnce(
      new ApiError({
        message: "Audio contains insufficient tonal information.",
        status_code: 422,
        error_code: "UNPROCESSABLE_AUDIO",
      })
    );

    const { result } = renderHook(() => useAnalysis());
    const validFile = new File(["valid-audio-data"], "silence.wav", { type: "audio/wav" });

    act(() => {
      result.current.handleFileChange(validFile);
    });

    await act(async () => {
      await result.current.analyzeAudio();
    });

    expect(result.current.status).toBe("error");
    expect(result.current.isAnalyzing).toBe(false);
    expect(result.current.errorMessage).toBe("Audio contains insufficient tonal information.");
    expect(result.current.errorDetail?.status_code).toBe(422);
  });

  it("resets analysis state on reset() call", () => {
    const { result } = renderHook(() => useAnalysis());
    const validFile = new File(["valid-audio-data"], "track.mp3", { type: "audio/mp3" });

    act(() => {
      result.current.handleFileChange(validFile);
    });
    expect(result.current.status).toBe("selected");

    act(() => {
      result.current.reset();
    });

    expect(result.current.status).toBe("idle");
    expect(result.current.audioFile).toBeNull();
    expect(result.current.analysisResult).toBeNull();
    expect(result.current.errorMessage).toBeNull();
  });
});
