import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

interface SwaraDistributionChartProps {
  pitchClassDistribution: Record<string, number>;
  dominantSwaras?: string[];
}

const SWARA_ORDER = ["S", "r", "R", "g", "G", "m", "M", "P", "d", "D", "n", "N"];
const SWARA_LABELS: Record<string, string> = {
  S: "Sa",
  r: "re",
  R: "Re",
  g: "ga",
  G: "Ga",
  m: "ma",
  M: "Ma'",
  P: "Pa",
  d: "dha",
  D: "Dha",
  n: "ni",
  N: "Ni",
};

export const SwaraDistributionChart: React.FC<SwaraDistributionChartProps> = ({
  pitchClassDistribution,
  dominantSwaras = [],
}) => {
  const chartData = SWARA_ORDER.map((symbol) => {
    const rawVal = pitchClassDistribution[symbol] || 0;
    const pct = Math.round(rawVal * 1000) / 10;
    const isDominant = dominantSwaras.includes(symbol) || dominantSwaras.includes(SWARA_LABELS[symbol]);

    return {
      symbol,
      label: SWARA_LABELS[symbol] || symbol,
      percentage: pct,
      isDominant,
    };
  });

  return (
    <div className="w-full h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
          <XAxis
            dataKey="label"
            stroke="#888888"
            fontSize={12}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            stroke="#888888"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            unit="%"
          />
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const data = payload[0].payload;
                return (
                  <div className="bg-popover text-popover-foreground p-2 rounded-md shadow-md border text-xs">
                    <p className="font-semibold">{data.label} ({data.symbol})</p>
                    <p className="text-muted-foreground">{data.percentage}% presence</p>
                    {data.isDominant && <p className="text-raga-primary font-medium mt-0.5">Dominant Swara</p>}
                  </div>
                );
              }
              return null;
            }}
          />
          <Bar dataKey="percentage" radius={[4, 4, 0, 0]}>
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.isDominant ? "#8B5CF6" : entry.percentage > 5 ? "#EC4899" : "#64748B"}
                opacity={entry.percentage > 0.5 ? 0.9 : 0.3}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default SwaraDistributionChart;
