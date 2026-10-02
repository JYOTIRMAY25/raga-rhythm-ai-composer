/**
 * Unified React Query music hook connecting UI components to live backend endpoints.
 */

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { musicService } from "../services/musicService";
import { Composition, CompositionSettings } from "../types/music";
import { Raga, Tala, AnalysisResponse, CompositionResponse } from "../types/api";
import { toast } from "../components/ui/use-toast";

export function useMusic() {
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [audioAnalysis, setAudioAnalysis] = useState<AnalysisResponse | null>(null);
  const [currentComposition, setCurrentComposition] = useState<CompositionResponse | Composition | null>(null);

  // Fetch all ragas from backend
  const ragasQuery = useQuery<Raga[]>({
    queryKey: ["ragas"],
    queryFn: () => musicService.getRagas(),
  });

  // Fetch all talas from backend
  const talasQuery = useQuery<Tala[]>({
    queryKey: ["talas"],
    queryFn: () => musicService.getTalas(),
  });

  // Fetch all styles
  const stylesQuery = useQuery({
    queryKey: ["styles"],
    queryFn: musicService.getStyles,
  });

  // Real synchronous audio analysis mutation
  const analyzeAudioMutation = useMutation({
    mutationFn: (file: File) => musicService.analyzeAudio(file),
    onSuccess: (data: AnalysisResponse) => {
      setAudioAnalysis(data);
      const ragaName = data.raga?.name;
      const confidence = Math.round((data.raga?.confidence ?? 0) * 100);
      toast({
        title: "Analysis Complete",
        description: ragaName
          ? `Detected Raga: ${ragaName} (${confidence}% confidence)`
          : "Audio analysis completed successfully.",
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Analysis Failed",
        description: error.message || "Could not analyze the audio file. Please try again.",
        variant: "destructive",
      });
      console.error("Analysis error:", error);
    },
  });

  // Composition generation mutation
  const generateCompositionMutation = useMutation({
    mutationFn: (settings: CompositionSettings) => musicService.generateComposition(settings),
    onSuccess: (data: CompositionResponse) => {
      setCurrentComposition(data);
      toast({
        title: "Composition Generated",
        description: `Successfully composed ${data.symbolic_composition.raga_name} in ${data.symbolic_composition.tala_name} (${data.symbolic_composition.events.length} swara events).`,
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Composition Generation Failed",
        description: error.message || "Could not generate composition.",
        variant: "destructive",
      });
    },
  });

  const handleFileChange = (file: File | null) => {
    setAudioFile(file);
    setAudioAnalysis(null);
  };

  const analyzeAudio = () => {
    if (audioFile) {
      analyzeAudioMutation.mutate(audioFile);
    } else {
      toast({
        title: "No File Selected",
        description: "Please select an audio file to analyze.",
        variant: "destructive",
      });
    }
  };

  const generateComposition = (settings: CompositionSettings) => {
    generateCompositionMutation.mutate(settings);
  };

  return {
    // Data
    ragas: ragasQuery.data || [],
    talas: talasQuery.data || [],
    styles: stylesQuery.data || [],
    audioFile,
    audioAnalysis,
    currentComposition,

    // Loading states
    isLoadingRagas: ragasQuery.isLoading,
    isLoadingTalas: talasQuery.isLoading,
    isLoadingStyles: stylesQuery.isLoading,
    isAnalyzing: analyzeAudioMutation.isPending,
    isGenerating: generateCompositionMutation.isPending,

    // Actions
    handleFileChange,
    analyzeAudio,
    generateComposition,

    // Reset functions
    resetAnalysis: () => setAudioAnalysis(null),
    resetComposition: () => setCurrentComposition(null),
  };
}
