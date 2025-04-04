
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from "@/components/ui/select";
import { Raga, Tala, Style, CompositionSettings } from "@/types/music";
import { AudioAnalysis } from "@/types/music";
import { Music2 } from "lucide-react";

interface CompositionGeneratorProps {
  ragas: Raga[];
  talas: Tala[];
  styles: Style[];
  isGenerating: boolean;
  onGenerate: (settings: CompositionSettings) => void;
  analysisResult?: AudioAnalysis | null;
  isLoadingMusic: boolean;
}

const CompositionGenerator = ({ 
  ragas, 
  talas, 
  styles, 
  isGenerating, 
  onGenerate,
  analysisResult,
  isLoadingMusic
}: CompositionGeneratorProps) => {
  // Set defaults, potentially from analysis results
  const [settings, setSettings] = useState<CompositionSettings>({
    raga: analysisResult?.raga?.id || (ragas.length > 0 ? ragas[0].id : ""),
    tala: analysisResult?.tala?.id || (talas.length > 0 ? talas[0].id : ""),
    style: styles.length > 0 ? styles[0].id : "",
    tempo: analysisResult?.tempo || 80,
    duration: 60, // Default 1 minute
    creativity: 50 // Medium creativity
  });

  const updateSetting = <K extends keyof CompositionSettings>(
    key: K, 
    value: CompositionSettings[K]
  ) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };
  
  const handleGenerate = () => {
    onGenerate(settings);
  };

  // Get the selected raga details for display
  const selectedRaga = ragas.find(r => r.id === settings.raga);

  return (
    <Card className="border-raga-secondary/20">
      <CardHeader className="bg-raga-light/50 dark:bg-raga-dark/30">
        <CardTitle className="text-raga-secondary flex items-center">
          <Music2 className="mr-2 h-5 w-5" />
          Generate Composition
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-6 space-y-6">
        {isLoadingMusic ? (
          <div className="py-4 text-center">
            <p className="text-muted-foreground">Loading music data...</p>
          </div>
        ) : (
          <>
            <div className="space-y-3">
              <div>
                <Label htmlFor="raga">Raga</Label>
                <Select 
                  value={settings.raga} 
                  onValueChange={(value) => updateSetting("raga", value)}
                  disabled={isGenerating}
                >
                  <SelectTrigger id="raga" className="w-full">
                    <SelectValue placeholder="Select a raga" />
                  </SelectTrigger>
                  <SelectContent>
                    {ragas.map((raga) => (
                      <SelectItem key={raga.id} value={raga.id}>
                        {raga.name} - {raga.mood}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {selectedRaga && (
                  <p className="text-sm text-muted-foreground mt-1">
                    {selectedRaga.description}
                  </p>
                )}
              </div>

              <div>
                <Label htmlFor="tala">Tala (Rhythm Pattern)</Label>
                <Select 
                  value={settings.tala} 
                  onValueChange={(value) => updateSetting("tala", value)}
                  disabled={isGenerating}
                >
                  <SelectTrigger id="tala" className="w-full">
                    <SelectValue placeholder="Select a tala" />
                  </SelectTrigger>
                  <SelectContent>
                    {talas.map((tala) => (
                      <SelectItem key={tala.id} value={tala.id}>
                        {tala.name} ({tala.beats} beats)
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="style">Style</Label>
                <Select 
                  value={settings.style} 
                  onValueChange={(value) => updateSetting("style", value)}
                  disabled={isGenerating}
                >
                  <SelectTrigger id="style" className="w-full">
                    <SelectValue placeholder="Select a style" />
                  </SelectTrigger>
                  <SelectContent>
                    {styles.map((style) => (
                      <SelectItem key={style.id} value={style.id}>
                        {style.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-6 pt-2">
              <div>
                <div className="flex justify-between">
                  <Label htmlFor="tempo">Tempo (BPM)</Label>
                  <span className="text-sm font-medium">{settings.tempo} BPM</span>
                </div>
                <Slider
                  id="tempo"
                  min={40}
                  max={200}
                  step={1}
                  value={[settings.tempo]}
                  onValueChange={(values) => updateSetting("tempo", values[0])}
                  disabled={isGenerating}
                  className="mt-2"
                />
                <div className="flex justify-between text-xs text-muted-foreground mt-1">
                  <span>Slow</span>
                  <span>Fast</span>
                </div>
              </div>

              <div>
                <div className="flex justify-between">
                  <Label htmlFor="duration">Duration</Label>
                  <span className="text-sm font-medium">
                    {Math.floor(settings.duration / 60)}:{String(settings.duration % 60).padStart(2, '0')}
                  </span>
                </div>
                <Slider
                  id="duration"
                  min={30}
                  max={300}
                  step={30}
                  value={[settings.duration]}
                  onValueChange={(values) => updateSetting("duration", values[0])}
                  disabled={isGenerating}
                  className="mt-2"
                />
                <div className="flex justify-between text-xs text-muted-foreground mt-1">
                  <span>30 seconds</span>
                  <span>5 minutes</span>
                </div>
              </div>

              <div>
                <div className="flex justify-between">
                  <Label htmlFor="creativity">Creativity Level</Label>
                  <span className="text-sm font-medium">
                    {settings.creativity < 33 ? "Conservative" : 
                     settings.creativity < 66 ? "Balanced" : "Experimental"}
                  </span>
                </div>
                <Slider
                  id="creativity"
                  min={0}
                  max={100}
                  step={1}
                  value={[settings.creativity]}
                  onValueChange={(values) => updateSetting("creativity", values[0])}
                  disabled={isGenerating}
                  className="mt-2"
                />
                <div className="flex justify-between text-xs text-muted-foreground mt-1">
                  <span>Traditional</span>
                  <span>Experimental</span>
                </div>
              </div>
            </div>

            <Button 
              onClick={handleGenerate} 
              disabled={isGenerating || !settings.raga || !settings.tala || !settings.style}
              className="w-full mt-4 bg-raga-primary hover:bg-raga-primary/90 text-white"
            >
              {isGenerating ? "Generating..." : "Generate Composition"}
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default CompositionGenerator;
