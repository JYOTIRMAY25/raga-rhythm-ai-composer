
import { Raga, Tala, Style } from "../types/music";

// Common ragas in Indian classical music
export const ragas: Raga[] = [
  {
    id: "bhairavi",
    name: "Bhairavi",
    time: "Morning",
    mood: "Serene, Devotional",
    description: "One of the most fundamental ragas in Hindustani classical music, evoking a sense of devotion and serenity.",
    notes: ["Sa", "Komal Re", "Komal Ga", "Ma", "Pa", "Komal Dha", "Komal Ni", "Sa"]
  },
  {
    id: "yaman",
    name: "Yaman",
    time: "Evening",
    mood: "Peaceful, Romantic",
    description: "A popular evening raga known for its pleasing and romantic mood.",
    notes: ["Sa", "Re", "Ga", "Ma Tivra", "Pa", "Dha", "Ni", "Sa"]
  },
  {
    id: "desh",
    name: "Desh",
    time: "Evening",
    mood: "Light, Joyful",
    description: "A light and popular raga that expresses joy and is often used in semi-classical compositions.",
    notes: ["Sa", "Re", "Ma", "Pa", "Ni Komal", "Sa"]
  },
  {
    id: "malkauns",
    name: "Malkauns",
    time: "Night",
    mood: "Deep, Meditative",
    description: "A serious midnight raga that creates a meditative and profound atmosphere.",
    notes: ["Sa", "Ga Komal", "Ma", "Dha Komal", "Ni Komal", "Sa"]
  },
  {
    id: "bageshri",
    name: "Bageshri",
    time: "Night",
    mood: "Longing, Romantic",
    description: "A beautiful night raga that evokes feelings of longing and romantic sentiment.",
    notes: ["Sa", "Re Komal", "Ga", "Ma", "Pa", "Dha", "Ni Komal", "Sa"]
  },
  {
    id: "durga",
    name: "Durga",
    time: "Evening",
    mood: "Strength, Confidence",
    description: "A pentatonic raga that evokes strength, valor, and confidence.",
    notes: ["Sa", "Re", "Ma", "Pa", "Dha", "Sa"]
  },
  {
    id: "todi",
    name: "Todi",
    time: "Morning",
    mood: "Serious, Profound",
    description: "A morning raga known for its serious and profound nature.",
    notes: ["Sa", "Re Komal", "Ga Komal", "Ma Tivra", "Pa", "Dha Komal", "Ni Komal", "Sa"]
  },
  {
    id: "kafi",
    name: "Kafi",
    time: "Any time",
    mood: "Versatile, Expressive",
    description: "A versatile raga that can express various moods and is adaptable to different styles.",
    notes: ["Sa", "Re", "Ga Komal", "Ma", "Pa", "Dha", "Ni Komal", "Sa"]
  }
];

// Common talas (rhythmic patterns)
export const talas: Tala[] = [
  {
    id: "teental",
    name: "Teental",
    beats: 16,
    description: "Most common tala in Hindustani classical music with 16 beats divided as 4+4+4+4",
    pattern: "Dha Dhin Dhin Dha | Dha Dhin Dhin Dha | Na Tin Tin Ta | Ta Dhin Dhin Dha"
  },
  {
    id: "jhaptaal",
    name: "Jhaptaal",
    beats: 10,
    description: "10 beat cycle divided as 2+3+2+3",
    pattern: "Dhi Na | Dhi Dhi Na | Ti Na | Dhi Dhi Na"
  },
  {
    id: "ektaal",
    name: "Ektaal",
    beats: 12,
    description: "12 beat cycle divided as 2+2+2+2+2+2",
    pattern: "Dhin Dhin | Dha Dha | Tin Tin | Ta Ta | Dhin Dhin | Dha Dha"
  },
  {
    id: "rupak",
    name: "Rupak",
    beats: 7,
    description: "7 beat cycle divided as 3+2+2",
    pattern: "Ti Ti Na | Dhi Na | Dhi Na"
  },
  {
    id: "dadra",
    name: "Dadra",
    beats: 6,
    description: "6 beat cycle divided as 3+3, commonly used in light classical music",
    pattern: "Dha Dhin Na | Dha Tin Na"
  },
  {
    id: "keherwa",
    name: "Keherwa",
    beats: 8,
    description: "8 beat cycle divided as 4+4, popular in folk and light classical music",
    pattern: "Dha Ge Na Ti | Na Ka Dhi Na"
  }
];

// Performance styles
export const styles: Style[] = [
  {
    id: "dhrupad",
    name: "Dhrupad",
    description: "The oldest and most austere form of Hindustani classical music, focusing on precise rhythm and pure notes."
  },
  {
    id: "khayal",
    name: "Khayal",
    description: "A more ornate and imaginative style that allows for greater improvisation and creativity."
  },
  {
    id: "thumri",
    name: "Thumri",
    description: "A semi-classical style that emphasizes romantic and devotional themes with more flexibility in expression."
  },
  {
    id: "ghazal",
    name: "Ghazal",
    description: "A poetic form set to music with romantic themes, blending classical and light elements."
  },
  {
    id: "tarana",
    name: "Tarana",
    description: "A rhythmic style using syllables inspired by Persian and Arabic phrases, focusing on rhythm and speed."
  },
  {
    id: "instrumental",
    name: "Instrumental",
    description: "Pure instrumental expression using traditional instruments like sitar, sarod, or bansuri."
  }
];

// Sample audio analysis responses (for demo purposes)
export const sampleAnalysis = {
  "bhairavi_analysis": {
    raga: ragas[0],
    tala: talas[0],
    tempo: 70,
    confidence: 0.85,
    notes: ["Sa", "Komal Re", "Komal Ga", "Ma", "Pa", "Komal Dha", "Komal Ni"]
  },
  "yaman_analysis": {
    raga: ragas[1],
    tala: talas[2],
    tempo: 80,
    confidence: 0.92,
    notes: ["Sa", "Re", "Ga", "Ma Tivra", "Pa", "Dha", "Ni"]
  }
};
