import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useAnalysis } from "./use-analysis";
import { api, ApiError } from "@/services/api";
import { AnalysisJobResponse, AnalysisResponse } from "@/types/api";

vi.mock("@/services/api", () => ({
  api: {
    analyzeAudio: vi.fn(),
    getAnalysisJob: vi.fn(),
    cancelAnalysisJob: vi.fn(),
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
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("initializes in idle state with null result, progress 0, and null errors", () => {
    const { result } = renderHook(() => useAnalysis());

    expect(result.current.status).toBe("idle");
    expect(result.current.audioFile).toBeNull();
    expect(result.current.analysisResult).toBeNull();
    expect(result.current.isAnalyzing).toBe(false);
    expect(result.current.progress).toBe(0);
    expect(result.current.currentStage).toBe("Initialization");
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

  it("creates job, polls status through stages, and completes with analysis result", async () => {
    const mockAnalysisPayload: AnalysisResponse = {
      analysis_id: "job-123",
      status: "completed",
      audio_metadata: {
        filename: "yaman.wav",
        duration_seconds: 12.0,
        sample_rate: 22050,
        channels: 1,
        format: "wav",
        is_silent: false,
        rms: 0.1,
        peak_amplitude: 0.8,
      },
      tonic: { note_name: "C", frequency_hz: 130.81, confidence: 0.95, is_ambiguous: false },
      pitch: {
        total_frames: 1000,
        voiced_frames: 800,
        voiced_percentage: 80.0,
        frame_rate: 225.0,
        method: "yin",
        downsampled_timestamps: [],
        downsampled_frequencies: [],
      },
      swara: {
        dominant_swaras: ["S", "G", "P"],
        active_swaras: ["S", "R", "G", "M'", "P", "D", "N"],
        total_segments: 15,
        mean_cents_deviation: 4.2,
        pitch_class_distribution: { S: 0.2, G: 0.3, P: 0.25 },
        transitions_top: [],
      },
      raga: {
        name: "Yaman",
        confidence: 0.92,
        is_ambiguous: false,
        aroha: ["N", "R", "G"],
        avaroha: ["S", "N", "D"],
        alternatives: [],
        motif_matches: [],
      },
      rhythm: {
        estimated_bpm: 80.0,
        laya: "Madhya",
        tempo_confidence: 0.85,
        total_onsets: 32,
        frame_rate: 100.0,
      },
      beat_grid: {
        beat_count: 32,
        beat_period: 0.75,
        bpm: 80.0,
        confidence: 0.9,
        selected_hypothesis: "1.0x",
        sam_timestamps: [0.0, 12.0],
      },
      tala: {
        name: "Teental",
        matras: 16,
        confidence: 0.88,
        is_ambiguous: false,
        khali_positions: [9],
        tali_positions: [1, 5, 13],
        candidates: [],
        tempo_hypothesis: "1.0x",
      },
      warnings: [],
      processing_time_ms: 250.0,
      created_at: new Date().toISOString(),
    };

    const initialJob: AnalysisJobResponse = {
      job_id: "job-123",
      status: "QUEUED",
      progress: 5,
      current_stage: "Audio preprocessing",
      created_at: new Date().toISOString(),
    };

    const processingJob: AnalysisJobResponse = {
      job_id: "job-123",
      status: "PROCESSING",
      progress: 50,
      current_stage: "Tonic resolution",
      created_at: new Date().toISOString(),
    };

    const completedJob: AnalysisJobResponse = {
      job_id: "job-123",
      status: "COMPLETED",
      progress: 100,
      current_stage: "Completed",
      created_at: new Date().toISOString(),
      result: mockAnalysisPayload,
    };

    vi.mocked(api.analyzeAudio).mockResolvedValueOnce(initialJob);
    vi.mocked(api.getAnalysisJob)
      .mockResolvedValueOnce(processingJob)
      .mockResolvedValueOnce(completedJob);

    const { result } = renderHook(() => useAnalysis());
    const validFile = new File(["valid-audio-data"], "yaman.wav", { type: "audio/wav" });

    act(() => {
      result.current.handleFileChange(validFile);
    });

    await act(async () => {
      await result.current.analyzeAudio();
    });

    expect(result.current.status).toBe("analyzing");
    expect(result.current.jobId).toBe("job-123");
    expect(result.current.progress).toBe(5);

    // Advance timer for first poll
    await act(async () => {
      vi.advanceTimersByTime(500);
    });

    expect(result.current.progress).toBe(50);
    expect(result.current.currentStage).toBe("Tonic resolution");

    // Advance timer for completion poll
    await act(async () => {
      vi.advanceTimersByTime(500);
    });

    expect(result.current.status).toBe("success");
    expect(result.current.isAnalyzing).toBe(false);
    expect(result.current.progress).toBe(100);
    expect(result.current.analysisResult).toEqual(mockAnalysisPayload);
  });

  it("handles job failure during asynchronous processing", async () => {
    const initialJob: AnalysisJobResponse = {
      job_id: "job-fail-1",
      status: "PROCESSING",
      progress: 10,
      current_stage: "Audio preprocessing",
      created_at: new Date().toISOString(),
    };

    const failedJob: AnalysisJobResponse = {
      job_id: "job-fail-1",
      status: "FAILED",
      progress: 15,
      current_stage: "Failed",
      created_at: new Date().toISOString(),
      error: {
        code: "INVALID_AUDIO_FORMAT",
        message: "Audio stream is corrupt.",
      },
    };

    vi.mocked(api.analyzeAudio).mockResolvedValueOnce(initialJob);
    vi.mocked(api.getAnalysisJob).mockResolvedValueOnce(failedJob);

    const { result } = renderHook(() => useAnalysis());
    const validFile = new File(["corrupt-data"], "corrupt.wav", { type: "audio/wav" });

    act(() => {
      result.current.handleFileChange(validFile);
    });

    await act(async () => {
      await result.current.analyzeAudio();
    });

    await act(async () => {
      vi.advanceTimersByTime(500);
    });

    expect(result.current.status).toBe("error");
    expect(result.current.errorMessage).toBe("Audio stream is corrupt.");
    expect(result.current.errorDetail?.error_code).toBe("INVALID_AUDIO_FORMAT");
  });

  it("supports cancellation of an active job and stops polling", async () => {
    const initialJob: AnalysisJobResponse = {
      job_id: "job-cancel-1",
      status: "PROCESSING",
      progress: 30,
      current_stage: "Pitch extraction",
      created_at: new Date().toISOString(),
    };

    vi.mocked(api.analyzeAudio).mockResolvedValueOnce(initialJob);
    vi.mocked(api.cancelAnalysisJob).mockResolvedValueOnce({
      job_id: "job-cancel-1",
      status: "CANCELLED",
      message: "Job was cancelled.",
    });

    const { result } = renderHook(() => useAnalysis());
    const validFile = new File(["data"], "test.wav", { type: "audio/wav" });

    act(() => {
      result.current.handleFileChange(validFile);
    });

    await act(async () => {
      await result.current.analyzeAudio();
    });

    expect(result.current.status).toBe("analyzing");

    await act(async () => {
      await result.current.cancelAnalysis();
    });

    expect(result.current.status).toBe("idle");
    expect(api.cancelAnalysisJob).toHaveBeenCalledWith("job-cancel-1");
  });

  it("protects against stale job responses when file is changed", async () => {
    const job1: AnalysisJobResponse = {
      job_id: "job-stale-1",
      status: "PROCESSING",
      progress: 20,
      current_stage: "Tonic estimation",
      created_at: new Date().toISOString(),
    };

    vi.mocked(api.analyzeAudio).mockResolvedValueOnce(job1);

    const { result } = renderHook(() => useAnalysis());
    const file1 = new File(["file1"], "file1.wav", { type: "audio/wav" });

    act(() => {
      result.current.handleFileChange(file1);
    });

    await act(async () => {
      await result.current.analyzeAudio();
    });

    // User selects a new file before poll returns
    const file2 = new File(["file2"], "file2.wav", { type: "audio/wav" });
    act(() => {
      result.current.handleFileChange(file2);
    });

    expect(result.current.status).toBe("selected");
    expect(result.current.jobId).toBeNull();
  });

  it("cleans up polling timers on unmount", async () => {
    const initialJob: AnalysisJobResponse = {
      job_id: "job-unmount",
      status: "PROCESSING",
      progress: 10,
      current_stage: "Audio preprocessing",
      created_at: new Date().toISOString(),
    };

    vi.mocked(api.analyzeAudio).mockResolvedValueOnce(initialJob);

    const { result, unmount } = renderHook(() => useAnalysis());
    const file = new File(["data"], "track.wav", { type: "audio/wav" });

    act(() => {
      result.current.handleFileChange(file);
    });

    await act(async () => {
      await result.current.analyzeAudio();
    });

    unmount();
    // Advance timers - no unhandled state updates on unmounted hook
    act(() => {
      vi.advanceTimersByTime(2000);
    });
  });

  it("drops in-flight fetch response if component unmounts before promise resolves", async () => {
    let resolveJobPoll!: (val: AnalysisJobResponse) => void;
    const delayedPollPromise = new Promise<AnalysisJobResponse>((resolve) => {
      resolveJobPoll = resolve;
    });

    const initialJob: AnalysisJobResponse = {
      job_id: "job-inflight",
      status: "PROCESSING",
      progress: 10,
      current_stage: "Audio preprocessing",
      created_at: new Date().toISOString(),
    };

    vi.mocked(api.analyzeAudio).mockResolvedValueOnce(initialJob);
    vi.mocked(api.getAnalysisJob).mockReturnValueOnce(delayedPollPromise);

    const { result, unmount } = renderHook(() => useAnalysis());
    const file = new File(["data"], "inflight.wav", { type: "audio/wav" });

    act(() => {
      result.current.handleFileChange(file);
    });

    await act(async () => {
      await result.current.analyzeAudio();
    });

    // Advance timer to trigger pollJobStatus
    act(() => {
      vi.advanceTimersByTime(500);
    });

    // Unmount while fetch is in-flight
    unmount();

    // Now resolve the in-flight fetch
    await act(async () => {
      resolveJobPoll({
        job_id: "job-inflight",
        status: "COMPLETED",
        progress: 100,
        current_stage: "Completed",
        created_at: new Date().toISOString(),
      });
    });

    // No error, clean drop
  });

  it("prevents delayed Job A poll response from overwriting newer Job B state", async () => {
    let resolveJobAPoll!: (val: AnalysisJobResponse) => void;
    const delayedJobAPromise = new Promise<AnalysisJobResponse>((resolve) => {
      resolveJobAPoll = resolve;
    });

    const jobA: AnalysisJobResponse = {
      job_id: "job-A",
      status: "PROCESSING",
      progress: 20,
      current_stage: "Pitch extraction",
      created_at: new Date().toISOString(),
    };

    const jobB: AnalysisJobResponse = {
      job_id: "job-B",
      status: "PROCESSING",
      progress: 5,
      current_stage: "Audio preprocessing",
      created_at: new Date().toISOString(),
    };

    vi.mocked(api.analyzeAudio)
      .mockResolvedValueOnce(jobA)
      .mockResolvedValueOnce(jobB);
    vi.mocked(api.getAnalysisJob).mockReturnValueOnce(delayedJobAPromise);

    const { result } = renderHook(() => useAnalysis());

    // Start Job A
    act(() => {
      result.current.handleFileChange(new File(["dataA"], "fileA.wav", { type: "audio/wav" }));
    });
    await act(async () => {
      await result.current.analyzeAudio();
    });
    expect(result.current.jobId).toBe("job-A");

    // Trigger poll for Job A
    act(() => {
      vi.advanceTimersByTime(500);
    });

    // While Job A poll is pending, user selects File B and starts Job B
    act(() => {
      result.current.handleFileChange(new File(["dataB"], "fileB.wav", { type: "audio/wav" }));
    });
    await act(async () => {
      await result.current.analyzeAudio();
    });
    expect(result.current.jobId).toBe("job-B");

    // Now resolve delayed Job A poll with COMPLETED
    await act(async () => {
      resolveJobAPoll({
        job_id: "job-A",
        status: "COMPLETED",
        progress: 100,
        current_stage: "Completed",
        created_at: new Date().toISOString(),
      });
    });

    // Job B state must remain intact; Job A completion must NOT overwrite Job B
    expect(result.current.jobId).toBe("job-B");
    expect(result.current.status).toBe("analyzing");
  });
});
