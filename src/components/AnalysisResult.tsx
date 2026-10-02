import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Music,
  Activity,
  BarChart3,
  Layers,
  AlertTriangle,
  Clock,
  Volume2,
  CheckCircle2,
  Sparkles,
} from "lucide-react";
import { AnalysisResponse, GeminiAnalysisExplanation } from "@/types/api";
import { AudioAnalysis } from "@/types/music";
import { api } from "@/services/api";
import SwaraDistributionChart from "./visualizations/SwaraDistributionChart";
import PitchContourChart from "./visualizations/PitchContourChart";
import TalaCycleVisualizer from "./visualizations/TalaCycleVisualizer";
import RagaCandidatesChart from "./visualizations/RagaCandidatesChart";
import AiExplanation from "./AiExplanation";

interface AnalysisResultProps {
  analysis: AnalysisResponse | AudioAnalysis;
}

// Type guard checking if payload is full AnalysisResponse
function isFullAnalysisResponse(data: AnalysisResponse | AudioAnalysis): data is AnalysisResponse {
  return "audio_metadata" in data && "tonic" in data;
}

const SWARA_NAME_MAP: Record<string, string> = {
  S: "Sa",
  r: "Komal Re (r)",
  R: "Shuddha Re (R)",
  g: "Komal Ga (g)",
  G: "Shuddha Ga (G)",
  m: "Shuddha Ma (m)",
  M: "Tivra Ma (M')",
  P: "Pa",
  d: "Komal Dha (d)",
  D: "Shuddha Dha (D)",
  n: "Komal Ni (n)",
  N: "Shuddha Ni (N)",
};

const AnalysisResult: React.FC<AnalysisResultProps> = ({ analysis }) => {
  const [explanation, setExplanation] = useState<GeminiAnalysisExplanation | null>(null);
  const [isLoadingExplanation, setIsLoadingExplanation] = useState<boolean>(false);

  useEffect(() => {
    if (isFullAnalysisResponse(analysis)) {
      setIsLoadingExplanation(true);
      api.explainAnalysis(analysis as unknown as Record<string, unknown>)
        .then((data) => setExplanation(data))
        .catch((err) => console.error("Could not fetch AI explanation:", err))
        .finally(() => setIsLoadingExplanation(false));
    }
  }, [analysis]);

  if (!isFullAnalysisResponse(analysis)) {
    // Legacy fallback rendering
    const confidencePercent = Math.round((analysis.confidence || 0) * 100);
    return (
      <Card className="border-raga-secondary/20">
        <CardHeader className="bg-raga-light/50 dark:bg-raga-dark/30">
          <CardTitle className="text-raga-secondary flex items-center justify-between">
            <span>Analysis Results</span>
            <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300">
              {confidencePercent}% Confidence
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-6 space-y-4">
          {analysis.raga && (
            <div>
              <h3 className="text-lg font-medium">Detected Raga</h3>
              <p className="text-2xl font-bold text-raga-primary">{analysis.raga.name}</p>
              <p className="text-sm text-muted-foreground mt-1">{analysis.raga.description}</p>
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  const confidencePercent = Math.round((analysis.raga?.confidence ?? 0) * 100);

  const getConfidenceBadgeColor = (pct: number) => {
    if (pct >= 75) return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300";
    if (pct >= 45) return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300";
    return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300";
  };

  const raga = analysis.raga;
  const tonic = analysis.tonic;
  const swara = analysis.swara;
  const rhythm = analysis.rhythm;
  const tala = analysis.tala;
  const meta = analysis.audio_metadata;
  const pitch = analysis.pitch;

  return (
    <Card className="border-raga-secondary/20 shadow-md">
      <CardHeader className="bg-raga-light/50 dark:bg-raga-dark/30 pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <div className="flex items-center space-x-2">
              <CardTitle className="text-2xl font-bold text-raga-primary">
                {raga.name || "Unknown Raga"}
              </CardTitle>
              {raga.thaat && (
                <Badge variant="outline" className="text-xs bg-white dark:bg-slate-800">
                  {raga.thaat} Thaat
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-1 flex items-center space-x-2">
              <span>Track: {meta.filename || "Uploaded audio"}</span>
              <span>•</span>
              <span>Duration: {meta.duration_seconds.toFixed(1)}s</span>
              <span>•</span>
              <span className="flex items-center">
                <Clock className="h-3 w-3 mr-1 inline" />
                {analysis.processing_time_ms.toFixed(0)} ms
              </span>
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <Badge className={getConfidenceBadgeColor(confidencePercent)}>
              {confidencePercent}% Raga Confidence
            </Badge>
          </div>
        </div>

        {raga.is_ambiguous && (
          <Alert variant="default" className="mt-3 py-2 bg-amber-50 dark:bg-amber-950/40 border-amber-300 dark:border-amber-800">
            <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
            <AlertTitle className="text-xs font-semibold text-amber-900 dark:text-amber-200">
              Ambiguous Raga Classification
            </AlertTitle>
            <AlertDescription className="text-xs text-amber-800 dark:text-amber-300">
              Melodic evidence exhibits close overlap with multiple allied ragas in this family.
            </AlertDescription>
          </Alert>
        )}
      </CardHeader>

      <CardContent className="pt-6 space-y-6">
        {/* Core Musicological Metadata Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 rounded-lg bg-slate-50 dark:bg-slate-900/60 border text-sm">
          <div>
            <span className="text-xs text-muted-foreground block">Resolved Sa (Tonic)</span>
            <span className="font-bold text-base text-foreground">
              {tonic.note_name} {tonic.frequency_hz ? `(${tonic.frequency_hz.toFixed(1)} Hz)` : ""}
            </span>
            <span className="text-[10px] text-muted-foreground block">
              Conf: {Math.round(tonic.confidence * 100)}% {tonic.is_ambiguous ? "• Ambiguous" : ""}
            </span>
          </div>

          <div>
            <span className="text-xs text-muted-foreground block">Tala & Beats</span>
            <span className="font-bold text-base text-foreground">
              {tala.name || "N/A"} {tala.matras ? `(${tala.matras} beats)` : ""}
            </span>
            <span className="text-[10px] text-muted-foreground block">
              Vibhag: {tala.vibhag_structure || "N/A"}
            </span>
          </div>

          <div>
            <span className="text-xs text-muted-foreground block">Estimated Tempo</span>
            <span className="font-bold text-base text-foreground">
              {rhythm.estimated_bpm ? `${rhythm.estimated_bpm} BPM` : "Unmetered"}
            </span>
            <span className="text-[10px] text-muted-foreground block">
              Laya: {rhythm.laya} ({Math.round(rhythm.tempo_confidence * 100)}% conf)
            </span>
          </div>

          <div>
            <span className="text-xs text-muted-foreground block">Time & Mood</span>
            <span className="font-semibold text-sm text-foreground block truncate">
              {raga.time || "N/A"}
            </span>
            <span className="text-[10px] text-muted-foreground block truncate">
              {raga.mood || "N/A"}
            </span>
          </div>
        </div>

        {/* Theoretical Notes / Scale */}
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-4 text-xs">
            {raga.vadi && (
              <div>
                <span className="text-muted-foreground">Vadi (King Note): </span>
                <Badge variant="secondary" className="font-mono">{SWARA_NAME_MAP[raga.vadi] || raga.vadi}</Badge>
              </div>
            )}
            {raga.samvadi && (
              <div>
                <span className="text-muted-foreground">Samvadi (Minister): </span>
                <Badge variant="secondary" className="font-mono">{SWARA_NAME_MAP[raga.samvadi] || raga.samvadi}</Badge>
              </div>
            )}
            {swara.dominant_swaras && swara.dominant_swaras.length > 0 && (
              <div>
                <span className="text-muted-foreground">Dominant in Audio: </span>
                <span className="font-medium text-foreground">{swara.dominant_swaras.join(", ")}</span>
              </div>
            )}
          </div>

          {raga.aroha && raga.aroha.length > 0 && (
            <div className="text-xs">
              <span className="text-muted-foreground font-semibold">Aroha (Ascent): </span>
              <span className="font-mono text-foreground">{raga.aroha.join(" - ")}</span>
            </div>
          )}

          {raga.avaroha && raga.avaroha.length > 0 && (
            <div className="text-xs">
              <span className="text-muted-foreground font-semibold">Avaroha (Descent): </span>
              <span className="font-mono text-foreground">{raga.avaroha.join(" - ")}</span>
            </div>
          )}
        </div>

        <Separator />

        {/* Detailed Visualizations Tabbed Section */}
        <Tabs defaultValue="swara" className="w-full">
          <TabsList className="grid grid-cols-5 mb-4">
            <TabsTrigger value="swara" className="text-xs flex items-center justify-center">
              <BarChart3 className="h-3.5 w-3.5 mr-1" />
              <span>Swara PCD</span>
            </TabsTrigger>
            <TabsTrigger value="pitch" className="text-xs flex items-center justify-center">
              <Activity className="h-3.5 w-3.5 mr-1" />
              <span>Pitch F0</span>
            </TabsTrigger>
            <TabsTrigger value="tala" className="text-xs flex items-center justify-center">
              <Layers className="h-3.5 w-3.5 mr-1" />
              <span>Tala Rhythm</span>
            </TabsTrigger>
            <TabsTrigger value="candidates" className="text-xs flex items-center justify-center">
              <Music className="h-3.5 w-3.5 mr-1" />
              <span>Candidates</span>
            </TabsTrigger>
            <TabsTrigger value="explanation" className="text-xs flex items-center justify-center">
              <Sparkles className="h-3.5 w-3.5 mr-1 text-purple-600 dark:text-purple-400" />
              <span>AI Insights</span>
            </TabsTrigger>
          </TabsList>

          {/* Swara PCD Distribution */}
          <TabsContent value="swara" className="space-y-4">
            <div>
              <h4 className="text-sm font-semibold mb-1">12-Tone Pitch Class Distribution (PCD)</h4>
              <p className="text-xs text-muted-foreground mb-3">
                Relative duration and prominence of all 12 microtonal swaras in this recording relative to detected Sa ({tonic.note_name}).
              </p>
              <SwaraDistributionChart
                pitchClassDistribution={swara.pitch_class_distribution}
                dominantSwaras={swara.dominant_swaras}
              />
            </div>

            {swara.transitions_top && swara.transitions_top.length > 0 && (
              <div className="pt-2 border-t">
                <span className="text-xs font-semibold text-foreground">Top Melodic Transitions: </span>
                <div className="flex flex-wrap gap-1.5 mt-1.5">
                  {swara.transitions_top.map((t, i) => (
                    <Badge key={`trans-${i}`} variant="outline" className="text-[11px] font-mono">
                      {t.from} → {t.to} ({t.count})
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </TabsContent>

          {/* Continuous Pitch Contour */}
          <TabsContent value="pitch" className="space-y-4">
            <div>
              <h4 className="text-sm font-semibold mb-1">Continuous Pitch Tracking (F0)</h4>
              <p className="text-xs text-muted-foreground mb-3">
                Extracted fundamental frequencies over time showing vocal intonation, ornamentation (*meend*), and melodic gestures.
              </p>
              <PitchContourChart
                timestamps={pitch.downsampled_timestamps}
                frequencies={pitch.downsampled_frequencies}
                tonicHz={tonic.frequency_hz}
              />
            </div>

            <div className="grid grid-cols-3 gap-2 text-xs p-3 rounded-md bg-slate-50 dark:bg-slate-900/60 border">
              <div>
                <span className="text-muted-foreground">Voiced Frames:</span>
                <span className="font-semibold block">{pitch.voiced_percentage.toFixed(1)}%</span>
              </div>
              <div>
                <span className="text-muted-foreground">Mean Frequency:</span>
                <span className="font-semibold block">{pitch.mean_f0_hz ? `${pitch.mean_f0_hz.toFixed(1)} Hz` : "N/A"}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Pitch Range:</span>
                <span className="font-semibold block">
                  {pitch.min_f0_hz && pitch.max_f0_hz ? `${pitch.min_f0_hz.toFixed(0)} - ${pitch.max_f0_hz.toFixed(0)} Hz` : "N/A"}
                </span>
              </div>
            </div>
          </TabsContent>

          {/* Tala & Rhythm Cycle */}
          <TabsContent value="tala" className="space-y-4">
            <TalaCycleVisualizer
              talaName={tala.name}
              matras={tala.matras}
              vibhagStructure={tala.vibhag_structure}
              theka={tala.theka}
              samPosition={tala.sam_position}
              khaliPositions={tala.khali_positions}
              taliPositions={tala.tali_positions}
              estimatedBpm={rhythm.estimated_bpm}
              laya={rhythm.laya}
            />
          </TabsContent>

          {/* Candidates & Motifs */}
          <TabsContent value="candidates" className="space-y-4">
            <div>
              <h4 className="text-sm font-semibold mb-1">Ranked Raga Candidates</h4>
              <p className="text-xs text-muted-foreground mb-3">
                Relative match probabilities calculated across swara consistency, PCD profile similarity, and pakad phrases.
              </p>
              <RagaCandidatesChart
                primaryRagaName={raga.name}
                primaryConfidence={raga.confidence}
                primaryThaat={raga.thaat}
                alternatives={raga.alternatives}
                isAmbiguous={raga.is_ambiguous}
              />
            </div>

            {raga.motif_matches && raga.motif_matches.length > 0 && (
              <div className="pt-3 border-t space-y-2">
                <h4 className="text-xs font-semibold text-foreground flex items-center">
                  <CheckCircle2 className="h-3.5 w-3.5 text-green-600 mr-1" />
                  Detected Catch Phrase (Pakad) Matches
                </h4>
                <div className="space-y-1.5">
                  {raga.motif_matches.map((mm, idx) => (
                    <div
                      key={`motif-${idx}`}
                      className="p-2 rounded bg-slate-50 dark:bg-slate-900/60 border text-xs flex items-center justify-between"
                    >
                      <div>
                        <span className="font-mono font-semibold text-raga-primary">{mm.motif_str}</span>
                        <span className="text-[10px] text-muted-foreground ml-2">({mm.match_type})</span>
                      </div>
                      <Badge variant="secondary" className="text-[10px]">
                        {Math.round(mm.similarity_score * 100)}% match
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </TabsContent>

          {/* AI Musical Commentary */}
          <TabsContent value="explanation" className="space-y-4">
            <AiExplanation explanation={explanation} isLoading={isLoadingExplanation} />
          </TabsContent>
        </Tabs>

        {/* Warnings List */}
        {analysis.warnings && analysis.warnings.length > 0 && (
          <div className="space-y-2 pt-2 border-t">
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Diagnostic Notices
            </h4>
            <div className="space-y-1.5">
              {analysis.warnings.map((w, idx) => (
                <div
                  key={`warn-${idx}`}
                  className="text-xs p-2 rounded bg-slate-100/60 dark:bg-slate-800/40 text-muted-foreground flex items-start space-x-2"
                >
                  <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0 mt-0.5" />
                  <span>
                    <strong className="text-foreground">{w.stage}:</strong> {w.message}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default AnalysisResult;
