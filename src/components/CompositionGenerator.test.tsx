import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import CompositionGenerator from "./CompositionGenerator";
import { Raga, Tala } from "@/types/api";
import { Style } from "@/types/music";

describe("CompositionGenerator Component", () => {
  const mockRagas: Raga[] = [
    {
      id: "yaman",
      name: "Yaman",
      thaat: "Kalyan",
      time: "Evening",
      vadi: "G",
      samvadi: "N",
      aroha: ["N.", "R", "G", "M'", "P", "D", "N", "S'"],
      avaroha: ["S'", "N", "D", "P", "M'", "G", "R", "S"],
      description: "A foundational evening raga expressing peace.",
    },
    {
      id: "bhairav",
      name: "Bhairav",
      thaat: "Bhairav",
      time: "Morning",
      vadi: "D",
      samvadi: "R",
      aroha: ["S", "r", "G", "m", "P", "d", "N", "S'"],
      avaroha: ["S'", "N", "d", "P", "m", "G", "r", "S"],
      description: "A serious, majestic morning raga.",
    },
  ];

  const mockTalas: Tala[] = [
    {
      id: "teental",
      name: "Teental",
      matras: 16,
      vibhag_structure: [4, 4, 4, 4],
      theka: ["Dha", "Dhin", "Dhin", "Dha"],
      tali: [1, 5, 13],
      khali: [9],
      description: "16-beat cycle.",
    },
  ];

  const mockStyles: Style[] = [
    { id: "classical", name: "Classical", description: "Traditional ICM style" },
    { id: "fusion", name: "Fusion", description: "Modern fusion style" },
  ];

  it("renders raga and tala selection controls and generate button", () => {
    const onGenerate = vi.fn();
    render(
      <CompositionGenerator
        ragas={mockRagas}
        talas={mockTalas}
        styles={mockStyles}
        isGenerating={false}
        onGenerate={onGenerate}
        isLoadingMusic={false}
      />
    );

    expect(screen.getByRole("heading", { name: /generate composition/i })).toBeInTheDocument();
    expect(screen.getByText("Tempo (BPM)")).toBeInTheDocument();
    expect(screen.getByText("Creativity Level")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^generate composition$/i })).toBeInTheDocument();
  });

  it("calls onGenerate with chosen settings on submit", () => {
    const onGenerate = vi.fn();
    render(
      <CompositionGenerator
        ragas={mockRagas}
        talas={mockTalas}
        styles={mockStyles}
        isGenerating={false}
        onGenerate={onGenerate}
        isLoadingMusic={false}
      />
    );

    const generateBtn = screen.getByRole("button", { name: /^generate composition$/i });
    fireEvent.click(generateBtn);

    expect(onGenerate).toHaveBeenCalledTimes(1);
    expect(onGenerate).toHaveBeenCalledWith(
      expect.objectContaining({
        raga: "yaman",
        tala: "teental",
        style: "classical",
      })
    );
  });

  it("disables generate button while generation is in progress", () => {
    const onGenerate = vi.fn();
    render(
      <CompositionGenerator
        ragas={mockRagas}
        talas={mockTalas}
        styles={mockStyles}
        isGenerating={true}
        onGenerate={onGenerate}
        isLoadingMusic={false}
      />
    );

    const generateBtn = screen.getByRole("button", { name: /generating\.\.\./i });
    expect(generateBtn).toBeDisabled();
  });

  it("renders Tuning Mode and Synthesis Timbre selection labels", () => {
    const onGenerate = vi.fn();
    render(
      <CompositionGenerator
        ragas={mockRagas}
        talas={mockTalas}
        styles={mockStyles}
        isGenerating={false}
        onGenerate={onGenerate}
        isLoadingMusic={false}
      />
    );

    expect(screen.getByText("Tuning Mode")).toBeInTheDocument();
    expect(screen.getByText("Synthesis Timbre")).toBeInTheDocument();
  });
});

