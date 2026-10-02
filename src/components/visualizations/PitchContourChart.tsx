import React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

interface PitchContourChartProps {
  timestamps: number[];
  frequencies: number[];
  tonicHz?: number | null;
}

export const PitchContourChart: React.FC<PitchContourChartProps> = ({
  timestamps,
  frequencies,
  tonicHz,
}) => {
  if (!timestamps || timestamps.length === 0 || !frequencies || frequencies.length === 0) {
    return (
      <div className="w-full h-48 flex items-center justify-center border border-dashed rounded-md text-xs text-muted-foreground">
        Pitch contour coordinates not available for this segment
      </div>
    );
  }

  const chartData = timestamps.map((t, idx) => ({
    time: t,
    timeLabel: `${t.toFixed(1)}s`,
    f0: frequencies[idx] && frequencies[idx] > 0 ? frequencies[idx] : null,
  }));

  const validFrequencies = frequencies.filter((f) => f && f > 0);
  const minF0 = validFrequencies.length > 0 ? Math.floor(Math.min(...validFrequencies) * 0.9) : 80;
  const maxF0 = validFrequencies.length > 0 ? Math.ceil(Math.max(...validFrequencies) * 1.1) : 350;

  return (
    <div className="w-full h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 20 }}>
          <XAxis
            dataKey="time"
            stroke="#888888"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            tickFormatter={(t) => `${Number(t).toFixed(1)}s`}
          />
          <YAxis
            domain={[minF0, maxF0]}
            stroke="#888888"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            unit=" Hz"
          />
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const data = payload[0].payload;
                return (
                  <div className="bg-popover text-popover-foreground p-2 rounded-md shadow-md border text-xs">
                    <p className="font-semibold">Time: {data.timeLabel}</p>
                    <p className="text-muted-foreground">F0: {data.f0 ? `${data.f0} Hz` : "Unvoiced"}</p>
                    {tonicHz && <p className="text-xs text-raga-primary mt-0.5">Sa (Tonic): {tonicHz} Hz</p>}
                  </div>
                );
              }
              return null;
            }}
          />
          {tonicHz && (
            <ReferenceLine
              y={tonicHz}
              stroke="#EC4899"
              strokeDasharray="3 3"
              label={{ value: `Sa (${tonicHz}Hz)`, fill: "#EC4899", fontSize: 10, position: "insideTopRight" }}
            />
          )}
          <Line
            type="monotone"
            dataKey="f0"
            stroke="#8B5CF6"
            strokeWidth={2}
            dot={false}
            connectNulls={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default PitchContourChart;
