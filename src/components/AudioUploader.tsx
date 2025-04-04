
import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Music } from "lucide-react";

interface AudioUploaderProps {
  onFileChange: (file: File | null) => void;
  onAnalyze: () => void;
  isAnalyzing: boolean;
}

const AudioUploader = ({ onFileChange, onAnalyze, isAnalyzing }: AudioUploaderProps) => {
  const [fileName, setFileName] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      const file = files[0];
      setFileName(file.name);
      onFileChange(file);
    } else {
      setFileName("");
      onFileChange(null);
    }
  };

  const handleButtonClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="w-full space-y-4 p-6 bg-white dark:bg-slate-900 rounded-lg shadow-md border border-slate-200 dark:border-slate-800">
      <h3 className="text-xl font-semibold mb-4 flex items-center">
        <Music className="mr-2 h-5 w-5 text-raga-primary" />
        Analyze Music
      </h3>
      
      <div className="flex items-center space-x-2">
        <Input 
          ref={fileInputRef}
          type="file" 
          accept="audio/*" 
          className="hidden"
          onChange={handleFileSelect}
        />
        <Button 
          variant="outline" 
          onClick={handleButtonClick}
          className="flex-1"
        >
          {fileName || "Select Audio File"}
        </Button>
        <Button 
          onClick={onAnalyze} 
          disabled={!fileName || isAnalyzing}
          variant="default"
          className="bg-raga-secondary hover:bg-raga-secondary/90"
        >
          {isAnalyzing ? "Analyzing..." : "Analyze"}
        </Button>
      </div>
      
      {fileName && (
        <div className="mt-4">
          <div className="text-sm text-muted-foreground">Selected file: {fileName}</div>
          <div className="mt-2 audio-waveform bg-raga-light dark:bg-slate-800 animate-pulse-subtle"></div>
        </div>
      )}
      
      <div className="text-sm text-muted-foreground mt-2">
        Upload an audio clip of Indian classical music to analyze the raga, tala, and tempo.
      </div>
    </div>
  );
};

export default AudioUploader;
