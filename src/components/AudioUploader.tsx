import React, { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Music, UploadCloud, AlertCircle, RefreshCw, CheckCircle2 } from "lucide-react";
import { AnalysisStatus } from "@/hooks/use-analysis";

interface AudioUploaderProps {
  onFileChange: (file: File | null) => void;
  onAnalyze: () => void;
  isAnalyzing: boolean;
  status?: AnalysisStatus;
  errorMessage?: string | null;
  onReset?: () => void;
}

const AudioUploader: React.FC<AudioUploaderProps> = ({
  onFileChange,
  onAnalyze,
  isAnalyzing,
  status = "idle",
  errorMessage = null,
  onReset,
}) => {
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

  const handleClear = () => {
    setFileName("");
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    onFileChange(null);
    onReset?.();
  };

  return (
    <div className="w-full space-y-4 p-6 bg-white dark:bg-slate-900 rounded-lg shadow-md border border-slate-200 dark:border-slate-800">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xl font-semibold flex items-center">
          <Music className="mr-2 h-5 w-5 text-raga-primary" />
          Analyze Music
        </h3>
        {fileName && !isAnalyzing && (
          <Button variant="ghost" size="sm" onClick={handleClear} className="text-xs text-muted-foreground hover:text-foreground">
            Clear File
          </Button>
        )}
      </div>

      <div className="flex flex-col sm:flex-row items-stretch sm:items-center space-y-2 sm:space-y-0 sm:space-x-2">
        <Input
          ref={fileInputRef}
          type="file"
          accept=".wav,.mp3,.flac,.ogg,.m4a,audio/*"
          className="hidden"
          onChange={handleFileSelect}
        />
        <Button
          variant="outline"
          onClick={handleButtonClick}
          disabled={isAnalyzing}
          className="flex-1 justify-start font-normal truncate"
        >
          <UploadCloud className="mr-2 h-4 w-4 shrink-0 text-muted-foreground" />
          <span className="truncate">{fileName || "Select Audio File (WAV, MP3, FLAC, OGG, M4A)"}</span>
        </Button>
        <Button
          onClick={onAnalyze}
          disabled={!fileName || isAnalyzing}
          variant="default"
          className="bg-raga-secondary hover:bg-raga-secondary/90 shrink-0 font-medium"
        >
          {isAnalyzing ? (
            <>
              <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
              Uploading & Analyzing...
            </>
          ) : status === "success" ? (
            <>
              <CheckCircle2 className="mr-2 h-4 w-4" />
              Re-Analyze
            </>
          ) : (
            "Analyze"
          )}
        </Button>
      </div>

      {isAnalyzing && (
        <div className="mt-4 p-4 rounded-md bg-raga-light/50 dark:bg-slate-800/60 border border-raga-secondary/20">
          <div className="flex items-center space-x-3">
            <RefreshCw className="h-5 w-5 text-raga-primary animate-spin" />
            <div>
              <p className="text-sm font-medium text-foreground">Processing Audio</p>
              <p className="text-xs text-muted-foreground">
                Running high-precision tonic resolution, swara tracking, raga classification, and beat analysis...
              </p>
            </div>
          </div>
          <div className="mt-3 audio-waveform bg-raga-light dark:bg-slate-800 animate-pulse-subtle h-2 rounded-full overflow-hidden"></div>
        </div>
      )}

      {status === "error" && errorMessage && (
        <Alert variant="destructive" className="mt-4">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Analysis Error</AlertTitle>
          <AlertDescription className="text-sm mt-1">{errorMessage}</AlertDescription>
        </Alert>
      )}

      {!isAnalyzing && status !== "error" && fileName && (
        <div className="mt-2 text-xs text-muted-foreground flex items-center space-x-1">
          <CheckCircle2 className="h-3.5 w-3.5 text-green-600 dark:text-green-400 shrink-0" />
          <span className="truncate">Ready for analysis: {fileName}</span>
        </div>
      )}

      <div className="text-xs text-muted-foreground mt-2">
        Upload an Indian classical music audio recording (max 25 MB) to extract tonic (*Sa*), 12-swara pitch distribution, raga, tempo, and tala structure.
      </div>
    </div>
  );
};

export default AudioUploader;
