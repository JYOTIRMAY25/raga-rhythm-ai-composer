import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import AudioUploader from "./AudioUploader";

describe("AudioUploader Component", () => {
  // AC2: Real component execution
  it("renders upload heading, file select button and disabled analyze button initially", () => {
    const onFileChange = vi.fn();
    const onAnalyze = vi.fn();
    render(<AudioUploader onFileChange={onFileChange} onAnalyze={onAnalyze} isAnalyzing={false} />);

    expect(screen.getByText("Analyze Music")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /select audio file/i })).toBeInTheDocument();
    const analyzeBtn = screen.getByRole("button", { name: /analyze/i });
    expect(analyzeBtn).toBeDisabled();
  });

  // Happy Path: File selection activates analyze button
  it("enables analyze button when a valid audio file is selected", () => {
    const onFileChange = vi.fn();
    const onAnalyze = vi.fn();
    const { container } = render(
      <AudioUploader onFileChange={onFileChange} onAnalyze={onAnalyze} isAnalyzing={false} />
    );

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const testFile = new File(["audio-bytes"], "bhairavi-alaap.mp3", { type: "audio/mp3" });

    fireEvent.change(input, { target: { files: [testFile] } });

    expect(onFileChange).toHaveBeenCalledWith(testFile);
    expect(screen.getByText(/Ready for analysis:\s*bhairavi-alaap\.mp3/i)).toBeInTheDocument();
    const analyzeBtn = screen.getByRole("button", { name: /analyze/i });
    expect(analyzeBtn).not.toBeDisabled();
  });

  // Adversarial: State / Loading
  it("displays 'Analyzing...' and disables button while analysis is in progress", () => {
    const onFileChange = vi.fn();
    const onAnalyze = vi.fn();
    const { container } = render(
      <AudioUploader onFileChange={onFileChange} onAnalyze={onAnalyze} isAnalyzing={true} />
    );

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const testFile = new File(["dummy"], "test.wav", { type: "audio/wav" });
    fireEvent.change(input, { target: { files: [testFile] } });

    const analyzingBtn = screen.getByRole("button", { name: /analyzing\.\.\./i });
    expect(analyzingBtn).toBeInTheDocument();
    expect(analyzingBtn).toBeDisabled();
  });

  // Adversarial: Deselection / Empty file list
  it("handles file deselection gracefully by disabling analyze button", () => {
    const onFileChange = vi.fn();
    const onAnalyze = vi.fn();
    const { container } = render(
      <AudioUploader onFileChange={onFileChange} onAnalyze={onAnalyze} isAnalyzing={false} />
    );

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const testFile = new File(["dummy"], "raga.mp3", { type: "audio/mp3" });

    // Select file
    fireEvent.change(input, { target: { files: [testFile] } });
    expect(screen.getByRole("button", { name: /^analyze$/i })).not.toBeDisabled();

    // Deselect file (empty FileList)
    fireEvent.change(input, { target: { files: [] } });
    expect(onFileChange).toHaveBeenLastCalledWith(null);
    expect(screen.getByRole("button", { name: /^analyze$/i })).toBeDisabled();
  });

  // Property / Invariant:
  // Invariant: For any filename F and analyzing state A, the analyze button is enabled if and only if (F is non-empty AND A is false).
  it("satisfies the invariant: analyze button enabled <=> (file is selected AND !isAnalyzing)", () => {
    const testCases = [
      { file: null, isAnalyzing: false, expectedEnabled: false },
      { file: null, isAnalyzing: true, expectedEnabled: false },
      { file: new File(["x"], "song1.wav", { type: "audio/wav" }), isAnalyzing: false, expectedEnabled: true },
      { file: new File(["x"], "song2.mp3", { type: "audio/mp3" }), isAnalyzing: true, expectedEnabled: false },
    ];

    for (const { file, isAnalyzing, expectedEnabled } of testCases) {
      const { unmount, container } = render(
        <AudioUploader onFileChange={() => {}} onAnalyze={() => {}} isAnalyzing={isAnalyzing} />
      );

      if (file) {
        const input = container.querySelector('input[type="file"]') as HTMLInputElement;
        fireEvent.change(input, { target: { files: [file] } });
      }

      const btn = screen.getByRole("button", { name: isAnalyzing ? /analyzing\.\.\./i : /^analyze$/i });
      const isEnabled = !btn.hasAttribute("disabled");
      expect(isEnabled).toBe(expectedEnabled);

      unmount();
    }
  });
});
