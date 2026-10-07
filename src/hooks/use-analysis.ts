/**
 * Centralized hook managing audio file selection, validation,
 * asynchronous job polling lifecycle, progress tracking, and cancellation.
 */

import { useState, useCallback, useRef, useEffect } from "react";
import { api, ApiError } from "@/services/api";
import {
  AnalysisJobResponse,
  AnalysisResponse,
  ApiErrorDetail,
} from "@/types/api";
import { toast } from "@/components/ui/use-toast";

export type AnalysisStatus =
  | "idle"
  | "selected"
  | "uploading"
  | "analyzing"
  | "success"
  | "error";

const MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024; // 25 MB
const ALLOWED_EXTENSIONS = [".wav", ".mp3", ".flac", ".ogg", ".m4a"];
const POLLING_INTERVAL_MS = 500;

export function useAnalysis() {
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResponse | null>(null);
  const [status, setStatus] = useState<AnalysisStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [errorDetail, setErrorDetail] = useState<ApiErrorDetail | null>(null);

  // Async job state tracking
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [currentStage, setCurrentStage] = useState<string>("Initialization");

  const activeJobIdRef = useRef<string | null>(null);
  const pollingTimerRef = useRef<NodeJS.Timeout | null>(null);

  const clearPolling = useCallback(() => {
    if (pollingTimerRef.current) {
      clearTimeout(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }
  }, []);

  // Cleanup polling on unmount and invalidate active job reference
  useEffect(() => {
    return () => {
      clearPolling();
      activeJobIdRef.current = null;
    };
  }, [clearPolling]);

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
    clearPolling();
    activeJobIdRef.current = null;
    setJobId(null);
    setProgress(0);
    setCurrentStage("Initialization");
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
  }, [clearPolling]);

  const pollJobStatus = useCallback(
    async (targetJobId: string) => {
      // Guard against stale jobs
      if (activeJobIdRef.current !== targetJobId) {
        return;
      }

      try {
        const jobStatus: AnalysisJobResponse = await api.getAnalysisJob(targetJobId);

        // Check again after fetch in case another job started
        if (activeJobIdRef.current !== targetJobId) {
          return;
        }

        setProgress(jobStatus.progress ?? 0);
        setCurrentStage(jobStatus.current_stage || "Processing");

        if (jobStatus.status === "COMPLETED") {
          clearPolling();
          if (jobStatus.result) {
            setAnalysisResult(jobStatus.result);
          }
          setStatus("success");
          setProgress(100);
          setCurrentStage("Completed");

          const ragaName = jobStatus.result?.raga?.name;
          const confidence = Math.round((jobStatus.result?.raga?.confidence ?? 0) * 100);

          toast({
            title: "Analysis Complete",
            description: ragaName
              ? `Detected Raga: ${ragaName} (${confidence}% confidence)`
              : "Audio analysis completed successfully.",
          });
        } else if (jobStatus.status === "FAILED") {
          clearPolling();
          setStatus("error");
          const failMsg =
            jobStatus.error?.message ||
            "An error occurred while processing the audio analysis.";
          setErrorMessage(failMsg);
          setErrorDetail({
            error_code: jobStatus.error?.code || "PROCESSING_ERROR",
            message: failMsg,
            status_code: 500,
            details: null,
            timestamp: new Date().toISOString(),
            request_id: jobStatus.request_id || null,
          });

          toast({
            title: "Analysis Failed",
            description: failMsg,
            variant: "destructive",
          });
        } else if (jobStatus.status === "CANCELLED") {
          clearPolling();
          setStatus("idle");
          setProgress(0);
          setCurrentStage("Cancelled");
          toast({
            title: "Analysis Cancelled",
            description: "The audio analysis job was cancelled.",
          });
        } else {
          // Still QUEUED or PROCESSING - schedule next poll
          pollingTimerRef.current = setTimeout(() => {
            pollJobStatus(targetJobId);
          }, POLLING_INTERVAL_MS);
        }
      } catch (err: unknown) {
        if (activeJobIdRef.current !== targetJobId) return;

        clearPolling();
        setStatus("error");
        let userFriendlyMessage = "Could not check analysis status. Backend server may be unreachable.";
        let detailObj: ApiErrorDetail | null = null;

        if (err instanceof ApiError) {
          userFriendlyMessage = err.message;
          detailObj = {
            error_code: err.errorCode,
            message: err.message,
            status_code: err.statusCode,
            details: err.details,
            timestamp: new Date().toISOString(),
            request_id: err.requestId || null,
          };
        } else if (err instanceof Error) {
          userFriendlyMessage = err.message;
        }

        setErrorMessage(userFriendlyMessage);
        setErrorDetail(detailObj);

        toast({
          title: "Status Check Failed",
          description: userFriendlyMessage,
          variant: "destructive",
        });
      }
    },
    [clearPolling]
  );

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

    clearPolling();
    setStatus("analyzing");
    setErrorMessage(null);
    setErrorDetail(null);
    setProgress(0);
    setCurrentStage("Audio preprocessing");

    try {
      const initialJob = await api.analyzeAudio(audioFile);
      const newJobId = initialJob.job_id;
      setJobId(newJobId);
      activeJobIdRef.current = newJobId;
      setProgress(initialJob.progress ?? 5);
      setCurrentStage(initialJob.current_stage || "Audio preprocessing");

      // Start polling for progress and completion
      pollingTimerRef.current = setTimeout(() => {
        pollJobStatus(newJobId);
      }, POLLING_INTERVAL_MS);
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
          request_id: err.requestId || null,
        };
      } else if (err instanceof Error) {
        userFriendlyMessage = err.message;
      }

      setErrorMessage(userFriendlyMessage);
      setErrorDetail(detailObj);

      toast({
        title: "Analysis Submission Failed",
        description: userFriendlyMessage,
        variant: "destructive",
      });
    }
  }, [audioFile, clearPolling, pollJobStatus]);

  const cancelAnalysis = useCallback(async () => {
    if (!jobId || status !== "analyzing") {
      return;
    }

    clearPolling();
    activeJobIdRef.current = null;
    try {
      await api.cancelAnalysisJob(jobId);
    } catch {
      // Ignore network errors on cancel
    } finally {
      setStatus("idle");
      setProgress(0);
      setCurrentStage("Cancelled");
      setJobId(null);
      toast({
        title: "Analysis Cancelled",
        description: "The audio analysis job has been cancelled.",
      });
    }
  }, [jobId, status, clearPolling]);

  const reset = useCallback(() => {
    clearPolling();
    activeJobIdRef.current = null;
    setJobId(null);
    setProgress(0);
    setCurrentStage("Initialization");
    setAudioFile(null);
    setAnalysisResult(null);
    setStatus("idle");
    setErrorMessage(null);
    setErrorDetail(null);
  }, [clearPolling]);

  return {
    audioFile,
    analysisResult,
    status,
    errorMessage,
    errorDetail,
    jobId,
    progress,
    currentStage,
    isAnalyzing: status === "analyzing" || status === "uploading",
    handleFileChange,
    analyzeAudio,
    cancelAnalysis,
    reset,
  };
}
