
import { useState, useRef, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Composition } from "@/types/music";
import { PlayCircle, PauseCircle, Download, Music3, Music4 } from "lucide-react";

interface CompositionPlayerProps {
  composition: Composition;
}

const CompositionPlayer = ({ composition }: CompositionPlayerProps) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  
  useEffect(() => {
    if (audioRef.current) {
      const audio = audioRef.current;
      
      const handleTimeUpdate = () => {
        setCurrentTime(audio.currentTime);
      };
      
      const handleDurationChange = () => {
        setDuration(audio.duration);
      };
      
      const handleEnded = () => {
        setIsPlaying(false);
        setCurrentTime(0);
      };
      
      audio.addEventListener("timeupdate", handleTimeUpdate);
      audio.addEventListener("durationchange", handleDurationChange);
      audio.addEventListener("ended", handleEnded);
      
      return () => {
        audio.removeEventListener("timeupdate", handleTimeUpdate);
        audio.removeEventListener("durationchange", handleDurationChange);
        audio.removeEventListener("ended", handleEnded);
      };
    }
  }, [audioRef]);
  
  const togglePlayPause = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };
  
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };
  
  // For demo purposes - we don't have actual audio files, so we're using a sample audio
  const audioSrc = "https://www.learningcontainer.com/wp-content/uploads/2020/02/Kalimba.mp3";
  
  const progressPercentage = duration ? (currentTime / duration) * 100 : 0;

  return (
    <Card className="border-raga-primary/20">
      <CardHeader className="bg-gradient-to-r from-raga-primary/10 to-raga-secondary/10 dark:from-raga-primary/5 dark:to-raga-secondary/5">
        <CardTitle className="text-raga-primary flex items-center justify-between">
          <span className="flex items-center">
            <Music3 className="mr-2 h-5 w-5" />
            Generated Composition
          </span>
          <Badge className="bg-raga-light text-raga-dark dark:bg-raga-dark dark:text-raga-light">
            {formatTime(duration)}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-6 space-y-4">
        <div className="space-y-2">
          <div className="text-lg font-medium">
            <span className="text-muted-foreground">Raga:</span> {composition.raga.name}
          </div>
          <div>
            <span className="text-muted-foreground">Tala:</span> {composition.tala.name} ({composition.tala.beats} beats)
          </div>
          <div>
            <span className="text-muted-foreground">Style:</span> {composition.style.name}
          </div>
          <div>
            <span className="text-muted-foreground">Tempo:</span> {composition.tempo} BPM
          </div>
        </div>
        
        <Separator />
        
        <div className="space-y-2">
          <div className="flex items-center">
            <Button 
              variant="ghost" 
              size="icon" 
              className="h-12 w-12 text-raga-primary" 
              onClick={togglePlayPause}
            >
              {isPlaying ? 
                <PauseCircle className="h-10 w-10" /> : 
                <PlayCircle className="h-10 w-10" />
              }
            </Button>
            <div className="flex-1 mx-2">
              <div className="h-2 w-full bg-raga-light dark:bg-slate-700 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-raga-primary transition-all duration-100"
                  style={{ width: `${progressPercentage}%` }}
                />
              </div>
              <div className="flex justify-between text-xs text-muted-foreground mt-1">
                <span>{formatTime(currentTime)}</span>
                <span>{formatTime(duration)}</span>
              </div>
            </div>
          </div>
          
          <audio ref={audioRef} src={audioSrc} preload="metadata" />
          
          <div className="audio-waveform mt-4 flex items-center justify-center">
            <Music4 className="h-16 w-16 text-raga-secondary/50 animate-float" />
          </div>
        </div>
      </CardContent>
      <CardFooter className="bg-raga-light/50 dark:bg-raga-dark/30 rounded-b-lg">
        <Button 
          variant="outline" 
          className="w-full flex items-center justify-center"
          onClick={() => { /* Would download the audio file in a real app */ }}
        >
          <Download className="mr-2 h-4 w-4" />
          Download Composition
        </Button>
      </CardFooter>
    </Card>
  );
};

export default CompositionPlayer;
