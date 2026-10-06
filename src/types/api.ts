/**
 * TypeScript API definitions strictly mirroring the backend Pydantic schemas.
 */

export interface HealthResponse {
  status: string;
  version: string;
  services: Record<string, string>;
  timestamp: string;
}

export interface ApiErrorDetail {
  error_code: string;
  message: string;
  status_code: number;
  details?: Record<string, unknown> | null;
  timestamp: string;
}

export interface NotImplementedResponse {
  status: string;
  error_code: string;
  message: string;
  endpoint: string;
  documentation_ref: string;
  timestamp: string;
}

export interface Raga {
  id: string;
  name: string;
  thaat?: string | null;
  time?: string | null;
  mood?: string | null;
  vadi?: string | null;
  samvadi?: string | null;
  swaras: string[];
  varjit: string[];
  aroha: string[];
  avaroha: string[];
  pakad_motifs: string[][];
  aliases: string[];
  description?: string | null;
}

export interface RagaListResponse {
  total: number;
  ragas: Raga[];
}

export interface Tala {
  id: string;
  name: string;
  matras: number;
  beats: number;
  vibhag_structure: number[];
  vibhag: string;
  sam_position: number;
  khali_positions: number[];
  tali_positions: number[];
  theka: string;
  pattern: string;
  theka_syllables: string[];
  aliases: string[];
  description?: string | null;
}

export interface TalaListResponse {
  total: number;
  talas: Tala[];
}

export interface AudioMetadata {
  filename?: string | null;
  duration_seconds: number;
  sample_rate: number;
  channels: number;
  format?: string | null;
  is_silent: boolean;
  rms: number;
  peak_amplitude: number;
}

export interface TonicResult {
  frequency_hz?: number | null;
  note_name: string;
  octave?: number | null;
  cents_deviation?: number | null;
  confidence: number;
  is_ambiguous: boolean;
  runner_up_hz?: number | null;
}

export interface PitchSummary {
  total_frames: number;
  voiced_frames: number;
  voiced_percentage: number;
  frame_rate: number;
  mean_f0_hz?: number | null;
  min_f0_hz?: number | null;
  max_f0_hz?: number | null;
  method: string;
  downsampled_timestamps: number[];
  downsampled_frequencies: number[];
}

export interface SwaraSummary {
  pitch_class_distribution: Record<string, number>;
  active_swaras: string[];
  total_segments: number;
  mean_cents_deviation: number;
  dominant_swaras: string[];
  transitions_top: Array<{ from: string; to: string; count: number }>;
}

export interface MotifEvidence {
  motif: string[];
  motif_str: string;
  match_type: string;
  matched_subsequence: string[];
  similarity_score: number;
  start_time_seconds?: number | null;
  end_time_seconds?: number | null;
}

export interface RagaAlternative {
  id: string;
  name: string;
  thaat?: string | null;
  confidence: number;
  composite_score: number;
}

export interface RagaResult {
  id?: string | null;
  name?: string | null;
  thaat?: string | null;
  time?: string | null;
  mood?: string | null;
  vadi?: string | null;
  samvadi?: string | null;
  aroha: string[];
  avaroha: string[];
  confidence: number;
  is_ambiguous: boolean;
  alternatives: RagaAlternative[];
  motif_matches: MotifEvidence[];
}

export interface RhythmSummary {
  estimated_bpm?: number | null;
  laya: string;
  tempo_confidence: number;
  total_onsets: number;
  frame_rate: number;
}

export interface BeatGridSummary {
  beat_count: number;
  beat_period: number;
  bpm?: number | null;
  confidence: number;
  selected_hypothesis: string;
  first_beat_time?: number | null;
  sam_timestamps: number[];
  cycle_length?: number | null;
}

export interface TalaCandidate {
  id: string;
  name: string;
  matras: number;
  confidence: number;
  composite_score: number;
}

export interface TalaResult {
  id?: string | null;
  name?: string | null;
  matras?: number | null;
  beats?: number | null;
  vibhag_structure?: string | null;
  theka?: string | null;
  sam_position?: number | null;
  khali_positions: number[];
  tali_positions: number[];
  confidence: number;
  is_ambiguous: boolean;
  candidates: TalaCandidate[];
  tempo_hypothesis: string;
}

export interface AnalysisWarning {
  stage: string;
  code: string;
  message: string;
}

export interface AnalysisResponse {
  analysis_id: string;
  status: "completed" | "processing" | "failed";
  audio_metadata: AudioMetadata;
  tonic: TonicResult;
  pitch: PitchSummary;
  swara: SwaraSummary;
  raga: RagaResult;
  rhythm: RhythmSummary;
  beat_grid: BeatGridSummary;
  tala: TalaResult;
  warnings: AnalysisWarning[];
  processing_time_ms: number;
  created_at: string;
}

export type AnalysisJobStatus = "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED" | "CANCELLED";

export interface JobErrorDetail {
  code: string;
  message: string;
}

export interface AnalysisJobResponse {
  job_id: string;
  status: AnalysisJobStatus;
  progress: number;
  current_stage: string;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  result?: AnalysisResponse | null;
  error?: JobErrorDetail | null;
}

export interface AnalysisJobCancelResponse {
  job_id: string;
  status: AnalysisJobStatus;
  message: string;
}


export interface GeminiAnalysisExplanation {
  available: boolean;
  summary: string;
  tonic_explanation: string;
  raga_explanation: string;
  swara_explanation: string;
  rhythm_explanation: string;
  tala_explanation: string;
  confidence_notes: string;
  warnings: string[];
  educational_notes: string[];
  model_used?: string | null;
  timestamp: string;
}

export interface SwaraEvent {
  cycle: number;
  vibhag: number;
  matra: number;
  subdivision: number;
  swara: string;
  octave: number;
  pitch_hz: number;
  duration_matras: number;
  theka_bol?: string | null;
  ornament?: string | null;
  is_vadi: boolean;
  is_samvadi: boolean;
  is_sam_landing: boolean;
}

export interface CompositionCycle {
  cycle_number: number;
  events: SwaraEvent[];
}

export interface ValidationDiagnostic {
  severity: "error" | "warning" | "info";
  rule: string;
  message: string;
  location?: string | null;
}

export interface ValidationResult {
  valid: boolean;
  swara_compliance_score: number;
  tala_alignment_score: number;
  sam_resolution_passed: boolean;
  diagnostics: ValidationDiagnostic[];
}

export interface SymbolicComposition {
  composition_id: string;
  title: string;
  raga_id: string;
  raga_name: string;
  thaat: string;
  tala_id: string;
  tala_name: string;
  matras: number;
  vibhag_structure: string;
  tempo_bpm: number;
  laya: string;
  tonic_note: string;
  tonic_hz: number;
  style: string;
  total_cycles: number;
  total_matras: number;
  duration_seconds: number;
  events: SwaraEvent[];
  cycles: CompositionCycle[];
  seed: number;
  validation: ValidationResult;
  created_at: string;
}

export interface CompositionRequest {
  raga_id: string;
  tala_id: string;
  tonic?: string | null;
  tonic_hz?: number | null;
  tempo_bpm?: number;
  duration_seconds?: number;
  style_id?: string;
  creativity_score?: number;
  seed?: number | null;
  tuning_mode?: "canonical" | "raga_aware";
  timbre?: "ensemble" | "flute" | "bowed";
}

export interface CompositionResponse {
  composition_id: string;
  title: string;
  metadata: Record<string, unknown>;
  symbolic_composition: SymbolicComposition;
  validation_result: ValidationResult;
  warnings: string[];
  audio_available?: boolean;
  audio_duration_seconds?: number;
  audio_url?: string | null;
  generated_at: string;
}

