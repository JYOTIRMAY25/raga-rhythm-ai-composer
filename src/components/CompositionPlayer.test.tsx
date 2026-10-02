import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CompositionPlayer from "./CompositionPlayer";
import { CompositionResponse, SymbolicComposition } from "@/types/api";

describe("CompositionPlayer Component", () => {
  const mockSymbolicComp: SymbolicComposition = {
    composition_id: "comp-uuid-1234",
    title: "Yaman in Teental Bandish",
    raga_id: "yaman",
    raga_name: "Yaman",
    thaat: "Kalyan",
    tala_id: "teental",
    tala_name: "Teental",
    matras: 16,
    vibhag_structure: "4+4+4+4",
    tempo_bpm: 84,
    laya: "Madhya",
    tonic_note: "C#",
    tonic_hz: 138.59,
    style: "bandish",
    total_cycles: 4,
    total_matras: 64,
    duration_seconds: 45.7,
    events: [
      {
        cycle: 1,
        vibhag: 1,
        matra: 1,
        subdivision: 0,
        swara: "N.",
        octave: -1,
        pitch_hz: 130.81,
        duration_matras: 1.0,
        theka_bol: "Dha",
        ornament: "straight",
        is_vadi: false,
        is_samvadi: true,
        is_sam_landing: true,
      },
      {
        cycle: 1,
        vibhag: 1,
        matra: 2,
        subdivision: 0,
        swara: "R",
        octave: 0,
        pitch_hz: 155.56,
        duration_matras: 1.0,
        theka_bol: "Dhin",
        ornament: "meend",
        is_vadi: false,
        is_samvadi: false,
        is_sam_landing: false,
      },
    ],
    cycles: [
      {
        cycle_number: 1,
        events: [],
      },
    ],
    seed: 108,
    validation: {
      valid: true,
      swara_compliance_score: 1.0,
      tala_alignment_score: 1.0,
      sam_resolution_passed: true,
      diagnostics: [],
    },
    created_at: "2026-10-01T12:00:00Z",
  };

  const mockResponse: CompositionResponse = {
    composition_id: "comp-uuid-1234",
    title: "Yaman in Teental Bandish",
    metadata: {},
    symbolic_composition: mockSymbolicComp,
    validation_result: mockSymbolicComp.validation,
    warnings: [],
    audio_available: true,
    audio_duration_seconds: 45.7,
    audio_url: "/api/v1/generate/wav?raga_id=yaman&tala_id=teental",
    generated_at: "2026-10-01T12:00:00Z",
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders composition metadata, raga, tala, tonic, bpm, and algorithmically synthesized badge", () => {
    render(<CompositionPlayer composition={mockResponse} />);

    expect(screen.getByText("Yaman in Teental Bandish")).toBeInTheDocument();
    expect(screen.getByText(/Algorithmically synthesized/i)).toBeInTheDocument();
    expect(screen.getByText(/Tonic Anchor \(Sa\):/i)).toBeInTheDocument();
    expect(screen.getAllByText(/C#\s*\(138\.6\s*Hz\)/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/4 Cycles\s*\(45\.7s\)/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Seed: 108/i).length).toBeGreaterThanOrEqual(1);
  });

  it("renders audio player action buttons (Play, Stop, Restart, Download WAV)", () => {
    render(<CompositionPlayer composition={mockResponse} />);

    expect(screen.getByRole("button", { name: /Play/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Stop/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Restart/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Download WAV/i })).toBeInTheDocument();
  });

  it("handles play, pause, and stop controls correctly", () => {
    render(<CompositionPlayer composition={mockResponse} />);

    const playBtn = screen.getByRole("button", { name: /Play/i });
    fireEvent.click(playBtn);

    // Once playing, button toggles to Pause
    expect(screen.getByRole("button", { name: /Pause/i })).toBeInTheDocument();

    const stopBtn = screen.getByRole("button", { name: /Stop/i });
    fireEvent.click(stopBtn);

    expect(screen.getByRole("button", { name: /Play/i })).toBeInTheDocument();
  });

  it("handles restart control", () => {
    render(<CompositionPlayer composition={mockResponse} />);

    const restartBtn = screen.getByRole("button", { name: /Restart/i });
    fireEvent.click(restartBtn);

    expect(screen.getByRole("button", { name: /Pause/i })).toBeInTheDocument();
  });

  it("triggers WAV download action on clicking Download WAV button", async () => {
    const fakeBlob = new Blob(["RIFF_WAVE_MOCK_BYTES"], { type: "audio/wav" });
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      blob: async () => fakeBlob,
    });

    // Mock URL createObjectURL and revokeObjectURL
    window.URL.createObjectURL = vi.fn().mockReturnValue("blob:http://localhost/fake-audio");
    window.URL.revokeObjectURL = vi.fn();

    render(<CompositionPlayer composition={mockResponse} />);

    const downloadBtn = screen.getByRole("button", { name: /Download WAV/i });
    fireEvent.click(downloadBtn);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining("/generate/wav"));
      expect(window.URL.createObjectURL).toHaveBeenCalled();
    });
  });

  it("handles download failure gracefully without crashing", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    global.fetch = vi.fn().mockRejectedValue(new Error("Network error"));

    render(<CompositionPlayer composition={mockResponse} />);

    const downloadBtn = screen.getByRole("button", { name: /Download WAV/i });
    fireEvent.click(downloadBtn);

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith("WAV Export error:", expect.any(Error));
    });

    consoleSpy.mockRestore();
  });

  it("handles repeated generation and updates displayed metadata when prop changes", () => {
    const { rerender } = render(<CompositionPlayer composition={mockResponse} />);
    expect(screen.getByText("Yaman in Teental Bandish")).toBeInTheDocument();
    expect(screen.getAllByText(/Seed: 108/i).length).toBeGreaterThanOrEqual(1);

    const newComp: SymbolicComposition = {
      ...mockSymbolicComp,
      composition_id: "comp-new-5678",
      title: "Bhairav in Ektaal Bandish",
      raga_id: "bhairav",
      raga_name: "Bhairav",
      tala_id: "ektaal",
      tala_name: "Ektaal",
      matras: 12,
      seed: 999,
    };

    const newResponse: CompositionResponse = {
      ...mockResponse,
      composition_id: "comp-new-5678",
      title: "Bhairav in Ektaal Bandish",
      symbolic_composition: newComp,
    };

    rerender(<CompositionPlayer composition={newResponse} />);

    expect(screen.getByText("Bhairav in Ektaal Bandish")).toBeInTheDocument();
    expect(screen.getAllByText(/Seed: 999/i).length).toBeGreaterThanOrEqual(1);
  });

  it("displays Raga-aware intonation badge when tuning_mode is raga_aware", () => {
    const ragaAwareResponse: CompositionResponse = {
      ...mockResponse,
      metadata: { tuning_mode: "raga_aware", timbre: "flute" },
    };

    render(<CompositionPlayer composition={ragaAwareResponse} />);

    expect(screen.getByText(/Raga-aware intonation/i)).toBeInTheDocument();
    expect(screen.getByText(/Algorithmically synthesized/i)).toBeInTheDocument();
  });
});

