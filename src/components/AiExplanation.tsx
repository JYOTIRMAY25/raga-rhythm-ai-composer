import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Sparkles, BookOpen, AlertCircle, Info, CheckCircle2, Music } from "lucide-react";
import { GeminiAnalysisExplanation } from "@/types/api";

interface AiExplanationProps {
  explanation: GeminiAnalysisExplanation | null;
  isLoading?: boolean;
}

export const AiExplanation: React.FC<AiExplanationProps> = ({
  explanation,
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <div className="p-6 rounded-lg bg-slate-50 dark:bg-slate-900/60 border text-center space-y-2">
        <Sparkles className="h-6 w-6 text-raga-primary mx-auto animate-spin" />
        <p className="text-sm font-medium">Generating Musicological Explanation...</p>
        <p className="text-xs text-muted-foreground">
          Synthesizing raga rules, tala cadence, and swara distribution insights...
        </p>
      </div>
    );
  }

  if (!explanation) {
    return (
      <div className="p-6 rounded-lg bg-slate-50 dark:bg-slate-900/60 border text-center text-xs text-muted-foreground">
        No AI commentary generated yet.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header card with status */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 p-4 rounded-lg bg-gradient-to-r from-purple-50 to-indigo-50 dark:from-purple-950/30 dark:to-indigo-950/30 border border-purple-200 dark:border-purple-800">
        <div className="flex items-center space-x-2">
          <Sparkles className="h-5 w-5 text-purple-600 dark:text-purple-400 shrink-0" />
          <div>
            <h4 className="font-semibold text-sm text-foreground">AI Musicological Commentary</h4>
            <p className="text-xs text-muted-foreground">
              Synthesized natural-language interpretation of machine analysis
            </p>
          </div>
        </div>
        <Badge
          variant={explanation.available ? "default" : "secondary"}
          className={`text-xs ${
            explanation.available
              ? "bg-purple-600 text-white"
              : "bg-slate-200 text-slate-800 dark:bg-slate-800 dark:text-slate-200"
          }`}
        >
          {explanation.available ? "Powered by Gemini AI" : "Rule-Engine Explanation"}
        </Badge>
      </div>

      {!explanation.available && (
        <Alert className="py-2.5 bg-blue-50/70 dark:bg-blue-950/30 border-blue-200 dark:border-blue-900 text-xs">
          <Info className="h-4 w-4 text-blue-600 dark:text-blue-400" />
          <AlertTitle className="text-xs font-semibold">Deterministic ICM Commentary Active</AlertTitle>
          <AlertDescription className="text-xs text-muted-foreground">
            Commentary is rendered directly from verified Indian classical music theory rules. Configure <code className="font-mono bg-slate-100 dark:bg-slate-800 px-1 py-0.5 rounded">GEMINI_API_KEY</code> for live AI synthesis.
          </AlertDescription>
        </Alert>
      )}

      {/* Executive Summary */}
      <Card className="border">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold flex items-center text-foreground">
            <Music className="h-4 w-4 mr-2 text-raga-primary" />
            Executive Analysis Summary
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs leading-relaxed text-foreground">{explanation.summary}</p>
        </CardContent>
      </Card>

      {/* Detailed Pillars Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
        <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900/60 border space-y-1">
          <span className="font-semibold text-foreground block">Tonic (Sa) & Acoustic Center:</span>
          <p className="text-muted-foreground leading-relaxed">{explanation.tonic_explanation}</p>
        </div>

        <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900/60 border space-y-1">
          <span className="font-semibold text-foreground block">Raga & Scale Aesthetics:</span>
          <p className="text-muted-foreground leading-relaxed">{explanation.raga_explanation}</p>
        </div>

        <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900/60 border space-y-1">
          <span className="font-semibold text-foreground block">Swara Distribution & Melodic Weight:</span>
          <p className="text-muted-foreground leading-relaxed">{explanation.swara_explanation}</p>
        </div>

        <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900/60 border space-y-1">
          <span className="font-semibold text-foreground block">Tala & Metric Cycles:</span>
          <p className="text-muted-foreground leading-relaxed">{explanation.tala_explanation}</p>
        </div>
      </div>

      {/* Educational Notes */}
      {explanation.educational_notes && explanation.educational_notes.length > 0 && (
        <Card className="border">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold flex items-center text-foreground">
              <BookOpen className="h-4 w-4 mr-2 text-indigo-600" />
              Musicological Insights for Classical Students
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1.5 text-xs text-muted-foreground">
              {explanation.educational_notes.map((note, idx) => (
                <li key={`edu-${idx}`} className="flex items-start space-x-2">
                  <CheckCircle2 className="h-3.5 w-3.5 text-green-600 dark:text-green-400 shrink-0 mt-0.5" />
                  <span>{note}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Warnings */}
      {explanation.warnings && explanation.warnings.length > 0 && (
        <div className="space-y-1.5">
          {explanation.warnings.map((w, idx) => (
            <div
              key={`exp-warn-${idx}`}
              className="text-[11px] p-2 rounded bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 text-amber-800 dark:text-amber-300 flex items-start space-x-1.5"
            >
              <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default AiExplanation;
