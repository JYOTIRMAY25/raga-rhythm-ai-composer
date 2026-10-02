import React from "react";
import { Badge } from "@/components/ui/badge";

interface TalaCycleVisualizerProps {
  talaName?: string | null;
  matras?: number | null;
  vibhagStructure?: string | null;
  theka?: string | string[] | null;
  samPosition?: number | null;
  khaliPositions?: number[];
  taliPositions?: number[];
  estimatedBpm?: number | null;
  laya?: string | null;
}

export const TalaCycleVisualizer: React.FC<TalaCycleVisualizerProps> = ({
  talaName = "Unknown Tala",
  matras = 16,
  vibhagStructure,
  theka,
  samPosition = 1,
  khaliPositions = [],
  taliPositions = [],
  estimatedBpm,
  laya,
}) => {
  const count = matras && matras > 0 ? matras : 16;
  const bols = Array.isArray(theka) ? theka : theka ? theka.split(" ") : [];

  // Parse vibhag partition counts
  const vibhags = vibhagStructure
    ? vibhagStructure.split("+").map((v) => parseInt(v.trim(), 10))
    : [4, 4, 4, 4];

  // Map each matra to its beat index, bol, and accent type
  let currentMatra = 1;
  const vibhagBeats: Array<Array<{ matra: number; bol: string; type: "sam" | "khali" | "tali" | "regular" }>> = [];

  vibhags.forEach((vSize) => {
    const section = [];
    for (let i = 0; i < vSize && currentMatra <= count; i++) {
      const m = currentMatra;
      const bol = bols[m - 1] || "";
      let type: "sam" | "khali" | "tali" | "regular" = "regular";

      if (m === samPosition) {
        type = "sam";
      } else if (khaliPositions.includes(m)) {
        type = "khali";
      } else if (taliPositions.includes(m)) {
        type = "tali";
      }

      section.push({ matra: m, bol, type });
      currentMatra++;
    }
    vibhagBeats.push(section);
  });

  return (
    <div className="w-full space-y-4 p-4 rounded-lg bg-slate-50 dark:bg-slate-900/60 border">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h4 className="font-semibold text-base">{talaName}</h4>
          <p className="text-xs text-muted-foreground">
            {count} Matras (Beats) • Vibhag: {vibhagStructure || "N/A"}
          </p>
        </div>
        <div className="flex items-center space-x-2">
          {estimatedBpm && (
            <Badge variant="outline" className="text-xs">
              {estimatedBpm} BPM
            </Badge>
          )}
          {laya && laya !== "Unknown" && (
            <Badge variant="secondary" className="text-xs">
              {laya} Laya
            </Badge>
          )}
        </div>
      </div>

      {/* Cyclic Measure Divisions */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 pt-2">
        {vibhagBeats.map((vGroup, vIdx) => (
          <div
            key={`vibhag-${vIdx}`}
            className="flex flex-col p-2.5 rounded-md bg-white dark:bg-slate-800 border shadow-sm"
          >
            <div className="text-[10px] font-mono font-medium text-muted-foreground uppercase mb-1.5 flex justify-between">
              <span>Vibhag {vIdx + 1}</span>
              <span>{vGroup.length} beats</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
              {vGroup.map((beat) => {
                const isSam = beat.type === "sam";
                const isKhali = beat.type === "khali";
                const isTali = beat.type === "tali";

                const badgeBg = isSam
                  ? "bg-raga-primary text-white font-bold"
                  : isKhali
                  ? "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200 border border-amber-300"
                  : isTali
                  ? "bg-purple-100 text-purple-900 dark:bg-purple-950 dark:text-purple-200"
                  : "bg-slate-100 dark:bg-slate-700/50 text-foreground";

                return (
                  <div
                    key={`beat-${beat.matra}`}
                    className={`flex flex-col items-center justify-center p-1 rounded text-center transition-all ${badgeBg}`}
                  >
                    <span className="text-[10px] opacity-75">
                      {isSam ? "Sam (1)" : isKhali ? "Khali (0)" : isTali ? `Tali (${beat.matra})` : beat.matra}
                    </span>
                    <span className="text-xs font-semibold truncate w-full">{beat.bol || "—"}</span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {theka && (
        <div className="text-xs text-muted-foreground pt-1 border-t">
          <span className="font-semibold text-foreground">Theka: </span>
          <span className="font-mono">{Array.isArray(theka) ? theka.join(" ") : theka}</span>
        </div>
      )}
    </div>
  );
};

export default TalaCycleVisualizer;
