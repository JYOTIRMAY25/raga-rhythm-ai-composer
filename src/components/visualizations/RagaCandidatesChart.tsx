import React from "react";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { RagaAlternative } from "@/types/api";

interface RagaCandidatesChartProps {
  primaryRagaName?: string | null;
  primaryConfidence?: number | null;
  primaryThaat?: string | null;
  alternatives?: RagaAlternative[];
  isAmbiguous?: boolean;
}

export const RagaCandidatesChart: React.FC<RagaCandidatesChartProps> = ({
  primaryRagaName,
  primaryConfidence = 0,
  primaryThaat,
  alternatives = [],
  isAmbiguous = false,
}) => {
  const topList = [
    {
      name: primaryRagaName || "Unknown Raga",
      confidence: Math.round((primaryConfidence || 0) * 100),
      thaat: primaryThaat,
      isPrimary: true,
    },
    ...alternatives.map((alt) => ({
      name: alt.name,
      confidence: Math.round(alt.confidence * 100),
      thaat: alt.thaat,
      isPrimary: false,
    })),
  ];

  return (
    <div className="w-full space-y-3">
      {topList.map((cand, idx) => (
        <div key={`cand-${idx}`} className="space-y-1">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center space-x-2">
              <span className={`font-medium ${cand.isPrimary ? "text-raga-primary font-bold" : "text-foreground"}`}>
                {cand.name}
              </span>
              {cand.thaat && (
                <Badge variant="outline" className="text-[10px] py-0 px-1.5 h-4">
                  {cand.thaat}
                </Badge>
              )}
              {cand.isPrimary && isAmbiguous && (
                <Badge variant="destructive" className="text-[10px] py-0 px-1.5 h-4">
                  Ambiguous
                </Badge>
              )}
            </div>
            <span className="font-mono text-muted-foreground">{cand.confidence}%</span>
          </div>
          <Progress
            value={cand.confidence}
            className={`h-2 ${cand.isPrimary ? "bg-raga-primary/20" : "bg-slate-200 dark:bg-slate-700"}`}
          />
        </div>
      ))}
    </div>
  );
};

export default RagaCandidatesChart;
