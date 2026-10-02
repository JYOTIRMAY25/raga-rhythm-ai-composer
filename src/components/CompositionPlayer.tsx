import React, { useState, useRef, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  PlayCircle,
  PauseCircle,
  Square,
  RotateCcw,
  Download,
  Music3,
  Volume2,
  CheckCircle2,
  Sparkles,
} from "lucide-react";
import { SymbolicComposition, CompositionResponse } from "@/types/api";
import { Composition } from "@/types/music";

interface CompositionPlayerProps {
  composition: SymbolicComposition | CompositionResponse | Composition;
}

function isSymbolicComposition(data: unknown): data is SymbolicComposition {
  return typeof data === "object" && data !== null && "events" in data && "raga_name" in data && Array.isArray((data as SymbolicComposition).events);
}

function isCompositionResponse(data: unknown): data is CompositionResponse {
  return typeof data === "object" && data !== null && "symbolic_composition" in data;
}

export const CompositionPlayer: React.FC<CompositionPlayerProps> = ({ composition }) => {
  const comp: SymbolicComposition | null = isCompositionResponse(composition)
    ? composition.symbolic_composition
    : isSymbolicComposition(composition)
    ? composition
    : null;

  const [isPlaying, setIsPlaying] = useState(false);
  const [currentEventIndex, setCurrentEventIndex] = useState(0);
  const [isDownloading, setIsDownloading] = useState(false);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const title = comp ? comp.title : (composition as Composition).raga?.name || "Generated Composition";
  const ragaName = comp ? comp.raga_name : (composition as Composition).raga?.name || "Yaman";
  const ragaId = comp ? comp.raga_id : (composition as Composition).raga?.id || "yaman";
  const talaName = comp ? comp.tala_name : (composition as Composition).tala?.name || "Teental";
  const talaId = comp ? comp.tala_id : (composition as Composition).tala?.id || "teental";
  const matras = comp ? comp.matras : (composition as Composition).tala?.beats || 16;
  const tempoBpm = comp ? comp.tempo_bpm : (composition as Composition).tempo || 84;
  const tonicNote = comp ? comp.tonic_note : "C";
  const tonicHz = comp ? comp.tonic_hz : 138.59;
  const totalCycles = comp ? comp.total_cycles : 4;
  const totalDurationSec = comp ? comp.duration_seconds : 60;
  const seed = comp ? comp.seed : 42;
  const events = comp?.events || [];

  // Play synthetic tone using Web Audio API
  const playTone = (freqHz: number, durationSec: number) => {
    try {
      if (!audioCtxRef.current) {
        const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        audioCtxRef.current = new AudioContextClass();
      }
      const ctx = audioCtxRef.current;
      if (ctx.state === "suspended") {
        ctx.resume();
      }

      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = "sine";
      osc.frequency.setValueAtTime(freqHz, ctx.currentTime);

      const now = ctx.currentTime;
      gain.gain.setValueAtTime(0.001, now);
      gain.gain.exponentialRampToValueAtTime(0.25, now + 0.04);
      gain.gain.exponentialRampToValueAtTime(0.001, now + durationSec - 0.02);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(now);
      osc.stop(now + durationSec);
    } catch (e) {
      console.warn("Web Audio synthesis error:", e);
    }
  };

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (audioCtxRef.current && audioCtxRef.current.state !== "closed") {
        audioCtxRef.current.close().catch(() => {});
      }
    };
  }, []);

  const scheduleNextEvent = (index: number) => {
    if (!comp || index >= events.length) {
      setIsPlaying(false);
      setCurrentEventIndex(0);
      return;
    }

    const currentEv = events[index];
    setCurrentEventIndex(index);

    const secondsPerMatra = 60.0 / tempoBpm;
    const durationSec = currentEv.duration_matras * secondsPerMatra;

    playTone(currentEv.pitch_hz, durationSec);

    timerRef.current = setTimeout(() => {
      scheduleNextEvent(index + 1);
    }, durationSec * 1000);
  };

  const handlePlay = () => {
    if (!isPlaying) {
      setIsPlaying(true);
      scheduleNextEvent(currentEventIndex);
    }
  };

  const handlePause = () => {
    if (isPlaying) {
      if (timerRef.current) clearTimeout(timerRef.current);
      setIsPlaying(false);
    }
  };

  const handleStop = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setIsPlaying(false);
    setCurrentEventIndex(0);
  };

  const handleRestart = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setCurrentEventIndex(0);
    setIsPlaying(true);
    scheduleNextEvent(0);
  };

  const tuningMode = (isCompositionResponse(composition) && (composition.metadata?.tuning_mode as string)) ||
    (comp && (composition as unknown as { audio_url?: string }).audio_url?.includes("tuning_mode=raga_aware") ? "raga_aware" : "canonical");
  const timbre = (isCompositionResponse(composition) && (composition.metadata?.timbre as string)) || "ensemble";

  const handleDownloadWav = async () => {
    setIsDownloading(true);
    try {
      const url = `/api/v1/generate/wav?raga_id=${encodeURIComponent(ragaId)}&tala_id=${encodeURIComponent(talaId)}&tempo_bpm=${tempoBpm}&duration_seconds=${Math.round(totalDurationSec)}&seed=${seed}&tuning_mode=${encodeURIComponent(tuningMode)}&timbre=${encodeURIComponent(timbre)}`;
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`WAV download failed with status ${response.status}`);
      }
      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = `composition_${ragaId}_${talaId}_seed${seed}.wav`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(downloadUrl);
    } catch (err) {
      console.error("WAV Export error:", err);
    } finally {
      setIsDownloading(false);
    }
  };

  const currentEvent = events[currentEventIndex];

  return (
    <Card className="border-raga-primary/20 shadow-md">
      <CardHeader className="bg-gradient-to-r from-raga-primary/10 to-raga-secondary/10 dark:from-raga-primary/5 dark:to-raga-secondary/5 pb-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
          <div>
            <CardTitle className="text-xl font-bold text-raga-primary flex items-center">
              <Music3 className="mr-2 h-5 w-5" />
              {title}
            </CardTitle>
            <p className="text-xs text-muted-foreground mt-0.5">
              Raga {ragaName} • Tala {talaName} ({matras} beats) • Tonic {tonicNote} ({tonicHz.toFixed(1)} Hz) • {tempoBpm} BPM • Duration: {totalDurationSec.toFixed(1)}s • Seed: {seed}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            {tuningMode === "raga_aware" && (
              <Badge className="bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-200">
                Raga-aware intonation
              </Badge>
            )}
            <Badge className="bg-purple-100 text-purple-900 dark:bg-purple-950 dark:text-purple-300 border border-purple-200">
              Algorithmically synthesized
            </Badge>
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-6 space-y-6">
        {/* Playback Controls & Status */}
        <div className="flex flex-wrap items-center gap-3 p-4 rounded-lg bg-slate-50 dark:bg-slate-900/60 border">
          {isPlaying ? (
            <Button
              size="icon"
              className="h-11 w-11 rounded-full bg-amber-600 hover:bg-amber-700 text-white shrink-0 shadow-md"
              onClick={handlePause}
              aria-label="Pause"
            >
              <PauseCircle className="h-6 w-6" />
            </Button>
          ) : (
            <Button
              size="icon"
              className="h-11 w-11 rounded-full bg-raga-primary hover:bg-raga-primary/90 text-white shrink-0 shadow-md"
              onClick={handlePlay}
              aria-label="Play"
            >
              <PlayCircle className="h-6 w-6" />
            </Button>
          )}

          <Button
            size="icon"
            variant="outline"
            className="h-10 w-10 shrink-0"
            onClick={handleStop}
            aria-label="Stop"
            title="Stop playback"
          >
            <Square className="h-4 w-4" />
          </Button>

          <Button
            size="icon"
            variant="outline"
            className="h-10 w-10 shrink-0"
            onClick={handleRestart}
            aria-label="Restart"
            title="Restart from beginning"
          >
            <RotateCcw className="h-4 w-4" />
          </Button>

          <Button
            variant="outline"
            size="sm"
            className="h-10 px-3 shrink-0 flex items-center space-x-1.5 border-purple-300 dark:border-purple-800 text-purple-700 dark:text-purple-300 hover:bg-purple-50 dark:hover:bg-purple-950/40"
            onClick={handleDownloadWav}
            disabled={isDownloading}
            aria-label="Download WAV"
          >
            <Download className="h-4 w-4 mr-1" />
            <span>{isDownloading ? "Exporting..." : "Download WAV"}</span>
          </Button>

          <div className="flex-1 min-w-[200px] space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-foreground flex items-center truncate">
                <Volume2 className="h-3.5 w-3.5 mr-1 text-raga-primary shrink-0" />
                {currentEvent ? (
                  <span>
                    Playing: <strong className="font-mono text-sm text-raga-primary">{currentEvent.swara}</strong>
                    {" "}({currentEvent.pitch_hz.toFixed(1)} Hz) • Bol: <em>{currentEvent.theka_bol || "—"}</em>
                  </span>
                ) : (
                  "Ready for playback"
                )}
              </span>
              <span className="text-muted-foreground font-mono shrink-0 ml-2">
                Event {currentEventIndex + 1} / {events.length || 1}
              </span>
            </div>

            {/* Progress Bar */}
            <div className="h-2 w-full bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-raga-primary transition-all duration-150"
                style={{
                  width: `${events.length > 0 ? ((currentEventIndex + 1) / events.length) * 100 : 0}%`,
                }}
              />
            </div>
          </div>
        </div>

        {/* Metric Cycle Info Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3 rounded-lg bg-slate-100/60 dark:bg-slate-800/40 text-xs border">
          <div>
            <span className="text-muted-foreground block">Raga & Scale:</span>
            <span className="font-bold text-foreground truncate block">
              {ragaName} ({comp?.thaat || "Kalyan"})
            </span>
          </div>
          <div>
            <span className="text-muted-foreground block">Tala & Laya:</span>
            <span className="font-bold text-foreground truncate block">
              {talaName} • {matras} Beats ({comp?.laya || "Madhya"})
            </span>
          </div>
          <div>
            <span className="text-muted-foreground block">Tonic Anchor (Sa):</span>
            <span className="font-bold text-foreground">
              {tonicNote} ({tonicHz.toFixed(1)} Hz)
            </span>
          </div>
          <div>
            <span className="text-muted-foreground block">Cycles & Duration:</span>
            <span className="font-bold text-foreground">
              {totalCycles} Cycles ({totalDurationSec.toFixed(1)}s)
            </span>
          </div>
        </div>

        <Separator />

        {/* Symbolic Score Grid */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider flex items-center">
              <Sparkles className="h-3.5 w-3.5 mr-1 text-purple-600" />
              Symbolic Tala Score & Swara Movement
            </h4>
            <span className="text-[11px] text-muted-foreground">
              Click play to step through metric cycles
            </span>
          </div>

          <div className="grid grid-cols-4 sm:grid-cols-8 md:grid-cols-16 gap-1.5 p-3 rounded-lg bg-slate-50 dark:bg-slate-900/60 border max-h-48 overflow-y-auto">
            {events.map((ev, idx) => {
              const isActive = idx === currentEventIndex;
              const isSam = ev.is_sam_landing || ev.matra === 1;

              return (
                <div
                  key={`score-ev-${idx}`}
                  className={`flex flex-col items-center justify-center p-1.5 rounded text-center transition-all ${
                    isActive
                      ? "bg-raga-primary text-white ring-2 ring-purple-400 scale-105 shadow-md"
                      : isSam
                      ? "bg-amber-100 dark:bg-amber-950/60 border border-amber-300 text-amber-900 dark:text-amber-200"
                      : "bg-white dark:bg-slate-800 border text-foreground"
                  }`}
                >
                  <span className="text-[9px] opacity-75">
                    {isSam ? "Sam (1)" : `m.${ev.matra}`}
                  </span>
                  <span className="text-xs font-mono font-bold">{ev.swara}</span>
                  <span className="text-[9px] truncate w-full text-muted-foreground">
                    {ev.theka_bol || "·"}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </CardContent>

      <CardFooter className="bg-slate-50 dark:bg-slate-900/40 rounded-b-lg text-xs text-muted-foreground flex justify-between items-center py-3">
        <span className="flex items-center">
          <CheckCircle2 className="h-3.5 w-3.5 mr-1 text-green-600" />
          Musicologically validated against {ragaName} aroha/avaroha rules
        </span>
        <span className="font-mono text-[11px]">Seed: {seed}</span>
      </CardFooter>
    </Card>
  );
};

export default CompositionPlayer;
