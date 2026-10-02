/**
 * Type-safe API Client for RagaRhythm AI FastAPI backend.
 */

import {
  AnalysisResponse,
  ApiErrorDetail,
  CompositionRequest,
  CompositionResponse,
  GeminiAnalysisExplanation,
  HealthResponse,
  NotImplementedResponse,
  Raga,
  RagaListResponse,
  Tala,
  TalaListResponse,
} from "@/types/api";

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || "/api/v1").replace(/\/+$/, "");

export class ApiError extends Error {
  public statusCode: number;
  public errorCode: string;
  public details?: Record<string, unknown> | null;

  constructor(errorDetail: ApiErrorDetail) {
    super(errorDetail.message);
    this.name = "ApiError";
    this.statusCode = errorDetail.status_code;
    this.errorCode = errorDetail.error_code;
    this.details = errorDetail.details;
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorDetail: ApiErrorDetail;
    try {
      const data = await response.json();
      errorDetail = {
        error_code: data.error_code || `HTTP_${response.status}`,
        message: data.message || response.statusText || "An unexpected error occurred.",
        status_code: response.status,
        details: data.details || null,
        timestamp: data.timestamp || new Date().toISOString(),
      };
    } catch {
      errorDetail = {
        error_code: `HTTP_${response.status}`,
        message: response.statusText || `Request failed with status ${response.status}`,
        status_code: response.status,
        details: null,
        timestamp: new Date().toISOString(),
      };
    }
    throw new ApiError(errorDetail);
  }
  return response.json() as Promise<T>;
}

export const api = {
  /**
   * Health and service readiness check.
   */
  getHealth: async (): Promise<HealthResponse> => {
    const res = await fetch(`${BASE_URL}/health`);
    return handleResponse<HealthResponse>(res);
  },

  /**
   * Retrieves ragas from the Knowledge Base catalog.
   */
  getRagas: async (params?: { thaat?: string; time?: string; search?: string }): Promise<Raga[]> => {
    const searchParams = new URLSearchParams();
    if (params?.thaat) searchParams.set("thaat", params.thaat);
    if (params?.time) searchParams.set("time", params.time);
    if (params?.search) searchParams.set("search", params.search);

    const queryStr = searchParams.toString();
    const url = `${BASE_URL}/ragas${queryStr ? `?${queryStr}` : ""}`;
    const res = await fetch(url);
    const data = await handleResponse<RagaListResponse>(res);
    return data.ragas;
  },

  /**
   * Retrieves a specific raga by ID.
   */
  getRaga: async (id: string): Promise<Raga> => {
    const res = await fetch(`${BASE_URL}/ragas/${encodeURIComponent(id)}`);
    return handleResponse<Raga>(res);
  },

  /**
   * Retrieves talas from the Knowledge Base catalog.
   */
  getTalas: async (params?: { matras?: number; search?: string }): Promise<Tala[]> => {
    const searchParams = new URLSearchParams();
    if (params?.matras) searchParams.set("matras", params.matras.toString());
    if (params?.search) searchParams.set("search", params.search);

    const queryStr = searchParams.toString();
    const url = `${BASE_URL}/talas${queryStr ? `?${queryStr}` : ""}`;
    const res = await fetch(url);
    const data = await handleResponse<TalaListResponse>(res);
    return data.talas;
  },

  /**
   * Retrieves a specific tala by ID.
   */
  getTala: async (id: string): Promise<Tala> => {
    const res = await fetch(`${BASE_URL}/talas/${encodeURIComponent(id)}`);
    return handleResponse<Tala>(res);
  },

  /**
   * Uploads and synchronously analyzes an audio file.
   */
  analyzeAudio: async (file: File): Promise<AnalysisResponse> => {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(`${BASE_URL}/analyze`, {
      method: "POST",
      body: formData,
    });
    return handleResponse<AnalysisResponse>(res);
  },

  /**
   * Generates natural-language AI explanation of music analysis using Gemini.
   */
  explainAnalysis: async (payload: Record<string, unknown>): Promise<GeminiAnalysisExplanation> => {
    const res = await fetch(`${BASE_URL}/explain`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<GeminiAnalysisExplanation>(res);
  },

  /**
   * Algorithmic composition generation producing validated symbolic score.
   */
  generateComposition: async (settings: CompositionRequest): Promise<CompositionResponse> => {
    const res = await fetch(`${BASE_URL}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    return handleResponse<CompositionResponse>(res);
  },
};
