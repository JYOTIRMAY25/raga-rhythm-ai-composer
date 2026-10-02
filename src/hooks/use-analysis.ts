/**
 * Centralized hook managing audio file selection, validation,
 * and API analysis lifecycle.
 */

import { useState, useCallback } from "react";
import { api, ApiError } from "@/services/api";
import { AnalysisResponse, ApiErrorDetail } from "@/types/api";
import { toast } from "@/components/ui/use-toast";

export type AnalysisStatus = "idle" | "selected" | "uploading" | "analyzing" | "success" | "error";

const MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024; // 25 MB
const ALLOWED_EXTENSIONS = [".wav", ".mp3", ".flac", ".ogg", ".m4a"];

export function useAnalysis() {
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResponse | null>(null);
  const [status, setStatus] = useState<AnalysisStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [errorDetail, setErrorDetail] = useState<ApiErrorDetail | null>(null);

  const validateFile = (file: File): string | null => {
    if (file.size === 0) {
      return "Selected file is empty (0 bytes).";
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      return `File size (${(file.size / (1024 * 1024)).toFixed(1)} MB) exceeds 25 MB limit.`;
    }
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `Unsupported file format '${ext}'. Please select a WAV, MP3, FLAC, OGG, or M4A file.`;
    }
    return null;
  };

  const handleFileChange = useCallback((file: File | null) => {
    setAudioFile(file);
    setAnalysisResult(null);
    setErrorMessage(null);
    setErrorDetail(null);

    if (file) {
      const validationErr = validateFile(file);
      if (validationErr) {
        setStatus("error");
        setErrorMessage(validationErr);
        toast({
          title: "Invalid File",
          description: validationErr,
          variant: "destructive",
        });
      } else {
        setStatus("selected");
      }
    } else {
      setStatus("idle");
    }
  }, []);

  const analyzeAudio = useCallback(async () => {
    if (!audioFile) {
      toast({
        title: "No File Selected",
        description: "Please select an audio file to analyze.",
        variant: "destructive",
      });
      return;
    }

    const validationErr = validateFile(audioFile);
    if (validationErr) {
      setStatus("error");
      setErrorMessage(validationErr);
      toast({
        title: "Invalid File",
        description: validationErr,
        variant: "destructive",
      });
      return;
    }

    setStatus("analyzing");
    setErrorMessage(null);
    setErrorDetail(null);

    try {
      const response = await api.analyzeAudio(audioFile);
      setAnalysisResult(response);
      setStatus("success");

      const ragaName = response.raga?.name;
      const confidence = Math.round((response.raga?.confidence ?? 0) * 100);

      toast({
        title: "Analysis Complete",
        description: ragaName
          ? `Detected Raga: ${ragaName} (${confidence}% confidence)`
          : "Audio analysis completed successfully.",
      });
    } catch (err: unknown) {
      setStatus("error");
      let userFriendlyMessage = "Could not analyze the audio file. Please ensure the backend server is running.";
      let detailObj: ApiErrorDetail | null = null;

      if (err instanceof ApiError) {
        userFriendlyMessage = err.message;
        detailObj = {
          error_code: err.errorCode,
          message: err.message,
          status_code: err.statusCode,
          details: err.details,
          timestamp: new Date().toISOString(),
        };
      } else if (err instanceof Error) {
        userFriendlyMessage = err.message;
      }

      setErrorMessage(userFriendlyMessage);
      setErrorDetail(detailObj);

      toast({
        title: "Analysis Failed",
        description: userFriendlyMessage,
        variant: "destructive",
      });
    }
  }, [audioFile]);

  const reset = useCallback(() => {
    setAudioFile(null);
    setAnalysisResult(null);
    setStatus("idle");
    setErrorMessage(null);
    setErrorDetail(null);
  }, []);

  return {
    audioFile,
    analysisResult,
    status,
    errorMessage,
    errorDetail,
    isAnalyzing: status === "analyzing" || status === "uploading",
    handleFileChange,
    analyzeAudio,
    reset,
  };
}
