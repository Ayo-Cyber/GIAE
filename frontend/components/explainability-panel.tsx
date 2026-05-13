"use client";

import { useMemo } from "react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Database,
  Microscope,
  GitBranch,
} from "lucide-react";
import type { Evidence, CompetingHypothesis } from "@/lib/types";
import { cn } from "@/lib/utils";

/* ───────── colours ───────── */
const SOURCE_PALETTE = [
  "#818cf8", // indigo-400
  "#34d399", // emerald-400
  "#fbbf24", // amber-400
  "#f472b6", // pink-400
  "#60a5fa", // blue-400
  "#a78bfa", // violet-400
  "#fb7185", // rose-400
];

function hashColour(source: string): string {
  let h = 0;
  for (let i = 0; i < source.length; i++) h = (h * 31 + source.charCodeAt(i)) | 0;
  return SOURCE_PALETTE[Math.abs(h) % SOURCE_PALETTE.length];
}

/* ───────── 1. Confidence composition donut ───────── */
interface CompositionDonutProps {
  evidence: Evidence[];
  score: number;
  level: string | null;
}

export function ConfidenceComposition({
  evidence,
  score,
  level,
}: CompositionDonutProps) {
  const data = useMemo(() => {
    if (evidence.length === 0) return [];
    // Group by source, sum confidence — this is what actually drives the score
    const bySource = new Map<string, number>();
    for (const ev of evidence) {
      bySource.set(ev.source, (bySource.get(ev.source) ?? 0) + ev.conf);
    }
    const total = Array.from(bySource.values()).reduce((a, b) => a + b, 0);
    return Array.from(bySource.entries())
      .map(([source, conf]) => ({
        name: source,
        value: conf,
        pct: total > 0 ? Math.round((conf / total) * 100) : 0,
        colour: hashColour(source),
      }))
      .sort((a, b) => b.value - a.value);
  }, [evidence]);

  if (data.length === 0) {
    return (
      <div className="bg-[#0f0f1e] border border-white/6 rounded-xl p-5 flex items-center gap-3">
        <AlertTriangle size={16} className="text-amber-400 shrink-0" />
        <div>
          <p className="text-sm font-medium text-white">No evidence sources</p>
          <p className="text-xs text-gray-500">
            Confidence cannot be decomposed — no plugin returned evidence for this gene.
          </p>
        </div>
      </div>
    );
  }

  const levelColour =
    level === "HIGH"
      ? "text-emerald-400"
      : level === "MODERATE"
      ? "text-amber-400"
      : level === "LOW"
      ? "text-indigo-400"
      : "text-purple-400";

  return (
    <div className="bg-[#0f0f1e] border border-white/6 rounded-xl p-5">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <Database size={14} className="text-gray-400" />
          <p className="text-xs text-gray-400 font-medium uppercase tracking-wider">
            Confidence composition
          </p>
        </div>
        <p className="text-xs text-gray-500">
          {evidence.length} {evidence.length === 1 ? "source" : "sources"}
        </p>
      </div>
      <p className="text-xs text-gray-600 mb-4">
        Where this gene's <span className="mono text-gray-400">{score.toFixed(2)}</span> score came from. Each slice = one evidence source's contribution.
      </p>

      <div className="flex flex-col sm:flex-row items-center gap-6">
        {/* Donut */}
        <div className="relative w-40 h-40 shrink-0">
          <ResponsiveContainer>
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                innerRadius={52}
                outerRadius={78}
                paddingAngle={data.length > 1 ? 2 : 0}
                stroke="none"
                labelLine={false}
                label={
                  data.length > 1
                    ? ({ cx, cy, midAngle, innerRadius, outerRadius, pct }: any) => {
                        if (pct < 12) return null; // skip tiny slices
                        const RADIAN = Math.PI / 180;
                        const r = innerRadius + (outerRadius - innerRadius) * 0.55;
                        const x = cx + r * Math.cos(-midAngle * RADIAN);
                        const y = cy + r * Math.sin(-midAngle * RADIAN);
                        return (
                          <text
                            x={x}
                            y={y}
                            fill="#0a0a14"
                            textAnchor="middle"
                            dominantBaseline="central"
                            style={{ fontSize: 10, fontWeight: 700 }}
                          >
                            {pct}%
                          </text>
                        );
                      }
                    : undefined
                }
              >
                {data.map((d) => (
                  <Cell key={d.name} fill={d.colour} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0a0a14",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: "8px",
                  fontSize: "11px",
                  color: "#fff",
                }}
                formatter={(value: number, name: string) => [
                  `${value.toFixed(2)} (${data.find((d) => d.name === name)?.pct}%)`,
                  name,
                ]}
              />
            </PieChart>
          </ResponsiveContainer>
          {/* Center label */}
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <p className={cn("text-2xl font-bold mono", levelColour)}>
              {score.toFixed(2)}
            </p>
            <p className="text-[10px] text-gray-500 uppercase tracking-wider">
              {level ?? "—"}
            </p>
          </div>
        </div>

        {/* Legend — bar style so percentages are obvious */}
        <div className="flex-1 w-full space-y-2.5 min-w-0">
          {data.map((d) => (
            <div key={d.name}>
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2 min-w-0">
                  <span
                    className="w-2.5 h-2.5 rounded-sm shrink-0"
                    style={{ backgroundColor: d.colour }}
                  />
                  <span className="text-xs font-medium text-gray-200 truncate">
                    {d.name}
                  </span>
                </div>
                <span className="text-xs mono text-gray-400 shrink-0 ml-2">
                  {d.pct}%
                </span>
              </div>
              <div className="h-1 bg-white/4 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${d.pct}%`, backgroundColor: d.colour }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ───────── 2. Reasoning chain ───────── */
interface ReasoningChainProps {
  steps: string[];
}

export function ReasoningChain({ steps }: ReasoningChainProps) {
  if (steps.length === 0) return null;
  return (
    <div className="bg-[#0f0f1e] border border-white/6 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <GitBranch size={14} className="text-gray-400" />
        <p className="text-xs text-gray-400 font-medium uppercase tracking-wider">
          Reasoning chain
        </p>
      </div>
      <ol className="space-y-3">
        {steps.map((step, i) => (
          <li key={i} className="flex gap-3">
            <div className="flex flex-col items-center shrink-0">
              <div className="w-6 h-6 rounded-full bg-indigo-600/15 border border-indigo-500/30 flex items-center justify-center">
                <span className="mono text-[10px] font-semibold text-indigo-400">
                  {i + 1}
                </span>
              </div>
              {i < steps.length - 1 && (
                <div className="flex-1 w-px bg-gradient-to-b from-indigo-500/25 to-transparent mt-1 min-h-3" />
              )}
            </div>
            <p className="text-xs text-gray-300 leading-relaxed pb-1.5">
              {step}
            </p>
          </li>
        ))}
      </ol>
    </div>
  );
}

/* ───────── 3. Competing hypotheses bar ───────── */
interface CompetingHypothesesProps {
  primary: { hypothesis: string; confidence: number };
  competing: CompetingHypothesis[];
}

export function CompetingHypothesesChart({
  primary,
  competing,
}: CompetingHypothesesProps) {
  if (competing.length === 0) return null;

  // Combine primary + competing for a unified bar chart
  const items = [
    {
      hypothesis: primary.hypothesis,
      confidence: primary.confidence,
      accepted: true,
      reason: null as string | null,
    },
    ...competing.map((c) => ({
      hypothesis: c.hypothesis,
      confidence: c.confidence,
      accepted: false,
      reason: c.reason_not_preferred,
    })),
  ].sort((a, b) => b.confidence - a.confidence);

  const max = Math.max(...items.map((i) => i.confidence), 1);

  return (
    <div className="bg-[#0f0f1e] border border-white/6 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-1">
        <Microscope size={14} className="text-gray-400" />
        <p className="text-xs text-gray-400 font-medium uppercase tracking-wider">
          Hypotheses considered
        </p>
      </div>
      <p className="text-xs text-gray-600 mb-4">
        The engine actively ranked {items.length} candidates before settling on
        the accepted one.
      </p>
      <div className="space-y-3">
        {items.map((item, i) => {
          const width = (item.confidence / max) * 100;
          return (
            <div key={i}>
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  {item.accepted ? (
                    <CheckCircle2
                      size={12}
                      className="text-emerald-400 shrink-0"
                    />
                  ) : (
                    <XCircle size={12} className="text-gray-600 shrink-0" />
                  )}
                  <span
                    className={cn(
                      "text-xs font-medium truncate",
                      item.accepted ? "text-white" : "text-gray-500"
                    )}
                  >
                    {item.hypothesis}
                  </span>
                </div>
                <span
                  className={cn(
                    "text-xs mono shrink-0 ml-2",
                    item.accepted ? "text-emerald-400" : "text-gray-600"
                  )}
                >
                  {(item.confidence * 100).toFixed(0)}%
                </span>
              </div>
              <div className="h-1.5 bg-white/4 rounded-full overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded-full transition-all",
                    item.accepted ? "bg-emerald-500" : "bg-gray-700"
                  )}
                  style={{ width: `${width}%` }}
                />
              </div>
              {!item.accepted && item.reason && (
                <p className="text-[10px] text-gray-600 mt-1 ml-5 italic">
                  Rejected: {item.reason}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ───────── 4. Uncertainty notes (small footnote-style) ───────── */
interface UncertaintyNotesProps {
  sources: string[];
}

export function UncertaintyNotes({ sources }: UncertaintyNotesProps) {
  if (sources.length === 0) return null;
  return (
    <div className="bg-amber-500/5 border border-amber-500/15 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        <AlertTriangle size={12} className="text-amber-400" />
        <p className="text-xs text-amber-300 font-medium uppercase tracking-wider">
          Sources of uncertainty
        </p>
      </div>
      <ul className="space-y-1">
        {sources.map((s, i) => (
          <li
            key={i}
            className="text-xs text-amber-200/80 leading-relaxed pl-3 relative"
          >
            <span className="absolute left-0 top-1.5 w-1 h-1 rounded-full bg-amber-400/60" />
            {s}
          </li>
        ))}
      </ul>
    </div>
  );
}
