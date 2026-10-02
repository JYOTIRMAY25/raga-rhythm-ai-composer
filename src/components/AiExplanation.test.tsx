import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import AiExplanation from "./AiExplanation";
import { GeminiAnalysisExplanation } from "@/types/api";

describe("AiExplanation Component", () => {
  const mockGeminiSuccess: GeminiAnalysisExplanation = {
    available: true,
    summary: "This performance presents an authentic exposition of Raga Bhairav in Teental.",
    tonic_explanation: "The tonic is centered at C# (138.6 Hz), anchoring the performance.",
    raga_explanation: "Bhairav exhibits prominent andolan on Komal Rishabh and Komal Dhaivat.",
    swara_explanation: "Heavy resting on Sa and Pa establishes steady stability.",
    tala_explanation: "Set to 16-beat Teental in Madhya laya at 80 BPM.",
    educational_notes: [
      "Bhairav is traditionally invoked during early morning sandhiprakash.",
      "The characteristic oscillatory andolan on komal rishabh requires microtonal precision."
    ],
    model_used: "gemini-2.5-flash",
  };

  const mockFallback: GeminiAnalysisExplanation = {
    available: false,
    summary: "Rule-based analysis indicates Raga Bhairav set to 16-beat Teental.",
    tonic_explanation: "Tonic detected at C# (138.6 Hz).",
    raga_explanation: "Features standard Bhairav aroha and avaroha.",
    swara_explanation: "S and P form primary anchors.",
    tala_explanation: "Teental 16 matras at 80 BPM.",
    educational_notes: ["Rule-based pedagogical reference."],
    model_used: "deterministic-rule-engine",
  };

  it("displays loading indicator when isLoading is true", () => {
    render(<AiExplanation explanation={null} isLoading={true} />);
    expect(screen.getByText(/Generating Musicological Explanation\.\.\./i)).toBeInTheDocument();
  });

  it("displays placeholder when explanation is null and not loading", () => {
    render(<AiExplanation explanation={null} isLoading={false} />);
    expect(screen.getByText(/No AI commentary generated yet\./i)).toBeInTheDocument();
  });

  it("renders live Gemini commentary when available is true", () => {
    render(<AiExplanation explanation={mockGeminiSuccess} isLoading={false} />);

    expect(screen.getByText(/AI Musicological Commentary/i)).toBeInTheDocument();
    expect(screen.getByText(/Powered by Gemini AI/i)).toBeInTheDocument();
    expect(screen.getByText(/This performance presents an authentic exposition/i)).toBeInTheDocument();
    expect(screen.getByText(/The tonic is centered at C# \(138\.6 Hz\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Bhairav exhibits prominent andolan/i)).toBeInTheDocument();
    expect(screen.getByText(/Bhairav is traditionally invoked during early morning/i)).toBeInTheDocument();
  });

  it("renders deterministic rule-engine banner when available is false", () => {
    render(<AiExplanation explanation={mockFallback} isLoading={false} />);

    expect(screen.getByText(/Rule-Engine Explanation/i)).toBeInTheDocument();
    expect(screen.getByText(/Deterministic ICM Commentary Active/i)).toBeInTheDocument();
    expect(screen.getByText(/Rule-based analysis indicates Raga Bhairav/i)).toBeInTheDocument();
  });
});
