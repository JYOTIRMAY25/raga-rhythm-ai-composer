
import { useState } from "react";
import { useMusic } from "@/hooks/use-music";
import AudioUploader from "@/components/AudioUploader";
import AnalysisResult from "@/components/AnalysisResult";
import CompositionGenerator from "@/components/CompositionGenerator";
import CompositionPlayer from "@/components/CompositionPlayer";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { Music, FileAudio, Play } from "lucide-react";

const Index = () => {
  const [activeTab, setActiveTab] = useState<string>("analyze");
  const { 
    ragas,
    talas,
    styles,
    audioFile,
    audioAnalysis,
    currentComposition,
    isLoadingRagas,
    isLoadingTalas,
    isLoadingStyles,
    isAnalyzing,
    isGenerating,
    handleFileChange,
    analyzeAudio,
    generateComposition
  } = useMusic();

  const isLoadingMusic = isLoadingRagas || isLoadingTalas || isLoadingStyles;

  return (
    <div className="min-h-screen mandala-bg">
      <div className="container max-w-6xl px-4 py-8 mx-auto">
        <header className="text-center mb-8">
          <h1 className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-raga-primary via-raga-secondary to-raga-accent bg-clip-text text-transparent">
            Raga Rhythm AI Composer
          </h1>
          <p className="mt-4 text-lg text-muted-foreground max-w-3xl mx-auto">
            A powerful tool for analysis and synthesis of Indian classical music. Analyze existing ragas or generate new compositions with customizable parameters.
          </p>
        </header>

        <Tabs 
          defaultValue="analyze" 
          value={activeTab} 
          onValueChange={setActiveTab}
          className="w-full"
        >
          <TabsList className="grid grid-cols-3 mb-8">
            <TabsTrigger value="analyze" className="flex items-center justify-center">
              <FileAudio className="mr-2 h-4 w-4" />
              <span>Analyze</span>
            </TabsTrigger>
            <TabsTrigger value="generate" className="flex items-center justify-center">
              <Music className="mr-2 h-4 w-4" />
              <span>Generate</span>
            </TabsTrigger>
            <TabsTrigger value="play" className="flex items-center justify-center" disabled={!currentComposition}>
              <Play className="mr-2 h-4 w-4" />
              <span>Play</span>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="analyze" className="space-y-8">
            <AudioUploader 
              onFileChange={handleFileChange}
              onAnalyze={analyzeAudio}
              isAnalyzing={isAnalyzing}
            />
            
            {audioAnalysis && (
              <>
                <Separator />
                <AnalysisResult analysis={audioAnalysis} />
              </>
            )}
          </TabsContent>

          <TabsContent value="generate" className="space-y-8">
            <CompositionGenerator 
              ragas={ragas}
              talas={talas}
              styles={styles}
              isGenerating={isGenerating}
              onGenerate={generateComposition}
              analysisResult={audioAnalysis}
              isLoadingMusic={isLoadingMusic}
            />
            
            {currentComposition && (
              <>
                <Separator />
                <div className="text-center">
                  <p className="text-muted-foreground">
                    Your composition has been generated! Go to the Play tab to listen.
                  </p>
                </div>
              </>
            )}
          </TabsContent>

          <TabsContent value="play">
            {currentComposition ? (
              <CompositionPlayer composition={currentComposition} />
            ) : (
              <div className="text-center py-12">
                <p className="text-muted-foreground">
                  No composition generated yet. Go to the Generate tab to create one.
                </p>
              </div>
            )}
          </TabsContent>
        </Tabs>

        <footer className="mt-16 text-center text-sm text-muted-foreground">
          <p>Powered by AI and Indian Classical Music theory.</p>
          <p className="mt-1">This application is a demonstration and does not connect to actual Google Cloud services.</p>
        </footer>
      </div>
    </div>
  );
};

export default Index;
