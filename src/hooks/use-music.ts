
import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { musicService } from '../services/musicService';
import { AudioAnalysis, Composition, CompositionSettings } from '../types/music';
import { toast } from '../components/ui/use-toast';

export function useMusic() {
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [audioAnalysis, setAudioAnalysis] = useState<AudioAnalysis | null>(null);
  const [currentComposition, setCurrentComposition] = useState<Composition | null>(null);

  // Fetch all ragas
  const ragasQuery = useQuery({
    queryKey: ['ragas'],
    queryFn: musicService.getRagas
  });

  // Fetch all talas
  const talasQuery = useQuery({
    queryKey: ['talas'],
    queryFn: musicService.getTalas
  });

  // Fetch all styles
  const stylesQuery = useQuery({
    queryKey: ['styles'],
    queryFn: musicService.getStyles
  });

  // Audio analysis mutation
  const analyzeAudioMutation = useMutation({
    mutationFn: (file: File) => musicService.analyzeAudio(file),
    onSuccess: (data) => {
      setAudioAnalysis(data);
      toast({
        title: "Analysis Complete",
        description: data.raga 
          ? `Detected Raga: ${data.raga.name} (${Math.round(data.confidence * 100)}% confidence)` 
          : "Could not determine the raga with confidence",
      });
    },
    onError: (error) => {
      toast({
        title: "Analysis Failed",
        description: "Could not analyze the audio file. Please try again.",
        variant: "destructive"
      });
      console.error("Analysis error:", error);
    }
  });

  // Composition generation mutation
  const generateCompositionMutation = useMutation({
    mutationFn: (settings: CompositionSettings) => musicService.generateComposition(settings),
    onSuccess: (data) => {
      setCurrentComposition(data);
      toast({
        title: "Composition Generated",
        description: `Successfully created a ${data.duration} second composition in ${data.raga.name} raga.`,
      });
    },
    onError: (error) => {
      toast({
        title: "Generation Failed",
        description: "Could not generate the composition. Please try again.",
        variant: "destructive"
      });
      console.error("Generation error:", error);
    }
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
        variant: "destructive"
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
    resetComposition: () => setCurrentComposition(null)
  };
}
