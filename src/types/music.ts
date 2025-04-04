
// Raga details
export interface Raga {
  id: string;
  name: string;
  time: string; // Time of day this raga is traditionally performed
  mood: string;
  description: string;
  notes: string[]; // Aroha (ascending scale) and Avaroha (descending scale)
}

// Tala (rhythmic pattern)
export interface Tala {
  id: string;
  name: string;
  beats: number;
  description: string;
  pattern: string;
}

// Performance style
export interface Style {
  id: string;
  name: string;
  description: string;
}

// Generated composition
export interface Composition {
  id: string;
  raga: Raga;
  tala: Tala;
  style: Style;
  tempo: number; // BPM
  duration: number; // In seconds
  creativity: number; // 0-100 scale
  audioUrl?: string;
  generatedAt: Date;
}

// For audio analysis
export interface AudioAnalysis {
  raga?: Raga;
  tala?: Tala;
  tempo?: number;
  confidence: number;
  notes: string[];
}

// Settings for composition generation
export interface CompositionSettings {
  raga: string;
  tala: string;
  style: string;
  tempo: number;
  duration: number;
  creativity: number;
}
