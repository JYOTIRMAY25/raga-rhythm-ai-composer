/**
 * Music service bridging the frontend application to the FastAPI backend API.
 */

import { api } from "./api";
import { ragas as fallbackRagas, talas as fallbackTalas, styles } from "../data/musicData";
import { Style, CompositionSettings } from "../types/music";
import { Raga, Tala, AnalysisResponse, CompositionResponse } from "../types/api";

export const musicService = {
  // Get all ragas from backend catalog (with fallback)
  getRagas: async (params?: { thaat?: string; time?: string; search?: string }): Promise<Raga[]> => {
    try {
      const liveRagas = await api.getRagas(params);
      if (liveRagas && liveRagas.length > 0) {
        return liveRagas;
      }
    } catch (e) {
      console.warn("Backend /api/v1/ragas unavailable, using catalog fallback:", e);
    }
    return fallbackRagas.map((r) => ({
      id: r.id,
      name: r.name,
      thaat: null,
      time: r.time,
      mood: r.mood,
      vadi: null,
      samvadi: null,
      swaras: r.notes || [],
      varjit: [],
      aroha: r.scale?.aroha || r.notes || [],
      avaroha: r.scale?.avaroha || r.notes || [],
      pakad_motifs: [],
      aliases: [],
      description: r.description,
    }));
  },

  // Get all talas from backend catalog (with fallback)
  getTalas: async (params?: { matras?: number; search?: string }): Promise<Tala[]> => {
    try {
      const liveTalas = await api.getTalas(params);
      if (liveTalas && liveTalas.length > 0) {
        return liveTalas;
      }
    } catch (e) {
      console.warn("Backend /api/v1/talas unavailable, using catalog fallback:", e);
    }
    return fallbackTalas.map((t) => ({
      id: t.id,
      name: t.name,
      matras: t.beats,
      beats: t.beats,
      vibhag_structure: [4, 4, 4, 4],
      vibhag: "4+4+4+4",
      sam_position: 1,
      khali_positions: [9],
      tali_positions: [1, 5, 13],
      theka: t.pattern,
      pattern: t.pattern,
      theka_syllables: t.pattern.split(" "),
      aliases: [],
      description: t.description,
    }));
  },

  // Get all styles
  getStyles: async (): Promise<Style[]> => {
    return styles;
  },

  // Get a specific raga by ID
  getRagaById: async (id: string): Promise<Raga | undefined> => {
    try {
      return await api.getRaga(id);
    } catch {
      const all = await musicService.getRagas();
      return all.find((r) => r.id === id);
    }
  },

  // Get a specific tala by ID
  getTalaById: async (id: string): Promise<Tala | undefined> => {
    try {
      return await api.getTala(id);
    } catch {
      const all = await musicService.getTalas();
      return all.find((t) => t.id === id);
    }
  },

  // Get a specific style by ID
  getStyleById: async (id: string): Promise<Style | undefined> => {
    return styles.find((style) => style.id === id);
  },

  // Asynchronous audio analysis polling via POST /api/v1/analyze & GET /api/v1/analysis/{id}
  analyzeAudio: async (audioFile: File): Promise<AnalysisResponse> => {
    const job = await api.analyzeAudio(audioFile);
    if (job.status === "COMPLETED" && job.result) {
      return job.result;
    }
    let currentJob = job;
    while (currentJob.status === "QUEUED" || currentJob.status === "PROCESSING") {
      await new Promise((resolve) => setTimeout(resolve, 300));
      currentJob = await api.getAnalysisJob(job.job_id);
    }
    if (currentJob.status === "COMPLETED" && currentJob.result) {
      return currentJob.result;
    }
    if (currentJob.status === "FAILED") {
      throw new Error(currentJob.error?.message || "Analysis failed.");
    }
    if (currentJob.status === "CANCELLED") {
      throw new Error("Analysis was cancelled.");
    }
    throw new Error("Analysis ended in an unexpected state.");
  },

  // Real algorithmic composition generation via POST /api/v1/generate
  generateComposition: async (settings: CompositionSettings): Promise<CompositionResponse> => {
    return await api.generateComposition({
      raga_id: settings.raga,
      tala_id: settings.tala,
      style_id: settings.style,
      tempo_bpm: settings.tempo,
      duration_seconds: settings.duration,
      creativity_score: settings.creativity,
    });
  },
};
