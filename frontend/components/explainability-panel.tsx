"use client";

import { useMemo, useState } from "react";
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
  CircleDotDashed,
  ChevronDown,
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

const EVIDENCE_LADDER = [
  {
    key: "genbank",
    label: "Curated annotation",
    hint: "GenBank or trusted reference record",
  },
  {
    key: "hmmer",
    label: "Domain search",
    hint: "HMMER / Pfam family evidence",
  },
  {
    key: "prosite",
    label: "Motif signature",
    hint: "PROSITE pattern or profile",
  },
  {
    key: "uniprot",
    label: "Reviewed homolog",
    hint: "UniProt or Swiss-Prot match",
  },
  {
    key: "interpro",
    label: "Integrated family",
    hint: "InterPro cross-database support",
  },
  {
    key: "esm",
    label: "Protein LM signal",
    hint: "Optional AI/embedding evidence",
  },
];

function hashColour(source: string): string {
  let h = 0;
  for (let i = 0; i < source.length; i++) h = (h * 31 + source.charCodeAt(i)) | 0;
  return SOURCE_PALETTE[Math.abs(h) % SOURCE_PALETTE.length];
}

// Maps waterfall row keys → all source/type strings the backend actually emits.
// tool_name comes from EvidenceProvenance.tool_name; type_val is the EvidenceType.value fallback.
const SOURCE_ALIASES: Record<string, string[]> = {
  genbank:  ["genbank"],                                       // genbank_parser, genbank_product, genbank_function, genbank_note
  hmmer:    ["hmmer", "domain_hit"],                           // tool_name="hmmer" or type="domain_hit"
  prosite:  ["giae_motif_scanner", "motif_match", "prosite"],  // tool_name or type fallback
  uniprot:  ["uniprot_api", "uniprot", "blast_homology",       // uniprot_api, diamond, blastp, homology
             "diamond", "blastp", "blast_local", "homology"],
  interpro: ["hmmer_web", "interpro"],                         // InterPro via HMMER web API
  esm:      ["esm", "structural_homology"],                    // ESM-2 embeddings
};

function sourceMatches(evidence: Evidence[], key: string) {
  const aliases = SOURCE_ALIASES[key] ?? [key];
  return evidence.find((ev) => {
    const haystack = `${ev.source} ${ev.label}`.toLowerCase();
    return aliases.some((alias) => haystack.includes(alias));
  });
}

/* ───────── 0. Evidence waterfall ───────── */
interface EvidenceLadderProps {
  evidence: Evidence[];
  isDark?: boolean;
}

const SOURCE_COLORS: Record<string, string> = {
  genbank:  "#34d399",
  hmmer:    "#818cf8",
  prosite:  "#fbbf24",
  uniprot:  "#22d3ee",
  interpro: "#a78bfa",
  esm:      "#f472b6",
};

function classifySource(source: string): string {
  const s = source.toLowerCase();
  for (const [key, aliases] of Object.entries(SOURCE_ALIASES)) {
    if (aliases.some((a) => s.includes(a))) return key;
  }
  return "other";
}

export function EvidenceLadder({ evidence, isDark }: EvidenceLadderProps) {
  if (evidence.length === 0) return null;

  const maxConf = Math.max(...evidence.map((e) => e.conf), 0.01);

  // One row per actual evidence item — fully data-driven
  const rows = evidence.map((ev) => {
    const cls   = classifySource(ev.source);
    const color = SOURCE_COLORS[cls] ?? hashColour(ev.source);
    const pct   = Math.round((ev.conf / maxConf) * 100);
    const step  = EVIDENCE_LADDER.find((s) => s.key === cls);
    return { ev, cls, color, pct, displayLabel: step?.label ?? ev.source };
  });

  // Which predefined categories got zero evidence?
  const coveredKeys = new Set(rows.map((r) => r.cls));
  const missingSteps = EVIDENCE_LADDER.filter((s) => !coveredKeys.has(s.key));

  return (
    <div className="bg-[#0f0f1e] border border-white/6 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-1">
        <CircleDotDashed size={14} className="text-cyan-300" />
        <p className="text-xs text-gray-400 font-medium uppercase tracking-wider">
          Evidence waterfall
        </p>
      </div>
      <p className="text-xs text-gray-600 mb-4">
        Bar width = confidence · colour = source class
      </p>

      <div className="space-y-2">
        {rows.map((row, i) => (
          <div key={i}>
            <div className="flex items-center gap-3 mb-0.5">
              <CheckCircle2 size={12} className="text-emerald-400 shrink-0" />
              <span className="text-xs font-medium text-gray-200 w-36 shrink-0 truncate">
                {row.displayLabel}
              </span>
              <div className="flex-1 h-2 bg-white/4 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${row.pct}%`, backgroundColor: row.color }}
                />
              </div>
              <span className="text-[10px] mono text-gray-400 w-10 text-right shrink-0">
                {row.ev.conf.toFixed(2)}
              </span>
            </div>
            {row.ev.label && (
              <p className="text-[11px] text-gray-600 pl-7 truncate leading-tight" title={row.ev.label}>
                {row.ev.label}
              </p>
            )}
          </div>
        ))}

        {/* Missing categories — compact chips */}
        {missingSteps.length > 0 && (
          <div className="pt-2.5 border-t border-white/5">
            <p className="text-[10px] text-gray-700 mb-1.5">No signal from:</p>
            <div className="flex flex-wrap gap-1.5">
              {missingSteps.map((s) => (
                <span key={s.key} className={cn(
                  "text-[10px] px-2 py-0.5 rounded border",
                  isDark
                    ? "bg-amber-500/5 border-amber-500/15 text-amber-700"
                    : "bg-white/[0.03] border-white/6 text-gray-700"
                )}>
                  {s.label}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
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
  const [expanded, setExpanded] = useState<Set<number>>(new Set([0]));
  if (steps.length === 0) return null;

  const toggle = (i: number) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });

  return (
    <div className="bg-[#0f0f1e] border border-white/6 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <GitBranch size={14} className="text-gray-400" />
        <p className="text-xs text-gray-400 font-medium uppercase tracking-wider">
          Reasoning chain
        </p>
        <span className="ml-auto text-[10px] text-gray-600">{steps.length} steps</span>
      </div>
      <ol className="space-y-1.5">
        {steps.map((step, i) => {
          const open     = expanded.has(i);
          const firstLine = step.split(".")[0] + (step.includes(".") ? "." : "");
          const rest      = step.slice(firstLine.length).trim();
          return (
            <li key={i}>
              <button
                onClick={() => toggle(i)}
                className="w-full flex items-start gap-3 text-left rounded-lg px-3 py-2.5 hover:bg-white/4 transition-colors group"
              >
                <div className="w-5 h-5 rounded-full bg-indigo-600/15 border border-indigo-500/30 flex items-center justify-center shrink-0 mt-0.5">
                  <span className="mono text-[9px] font-semibold text-indigo-400">{i + 1}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-gray-300 leading-relaxed">{firstLine}</p>
                  {open && rest && (
                    <p className="text-xs text-gray-500 leading-relaxed mt-1">{rest}</p>
                  )}
                </div>
                {rest && (
                  <ChevronDown
                    size={12}
                    className={cn("text-gray-600 shrink-0 mt-1 transition-transform", open && "rotate-180")}
                  />
                )}
              </button>
            </li>
          );
        })}
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

/* ───────── 4b. Dark matter research card ───────── */
interface DarkMatterCardProps {
  gene: {
    name: string;
    locus: string;
    start?: number | null;
    end?: number | null;
    strand?: number | null;
    length?: number | null;
  };
}

const EXPERIMENTS = [
  { label: "Overexpression", desc: "Clone into pET vector, express in E. coli BL21, check for growth phenotype and solubility." },
  { label: "Deletion mutant", desc: "Create in-frame knockout; compare growth, stress response, and metabolite profile against WT." },
  { label: "Pull-down / co-IP", desc: "Tag with His6 or FLAG, pull down from native lysate to identify interacting partners." },
  { label: "Transcriptomics", desc: "Check RNA-seq data for expression under stress, phage infection, or stationary phase." },
];

function primerParams(length: number | null | undefined) {
  if (!length) return null;
  const gcHint = length > 600 ? "aim for 50–60% GC" : "aim for 45–55% GC";
  const tmHint = "Tm 58–62 °C";
  const overlapNote = length > 1000 ? "Consider nested PCR for fragments > 1 kb." : null;
  return { gcHint, tmHint, overlapNote };
}

export function DarkMatterResearchCard({ gene }: DarkMatterCardProps) {
  const primers = primerParams(gene.length);
  const esmUrl  = `https://esmatlas.com/resources?action=fold`;
  const ncbiUrl = `https://www.ncbi.nlm.nih.gov/protein/?term=${encodeURIComponent(gene.locus)}`;

  return (
    <div className="bg-[#0f0f1e] border border-amber-500/15 rounded-xl p-5 space-y-5">
      <div className="flex items-center gap-2">
        <AlertTriangle size={14} className="text-amber-400" />
        <p className="text-xs text-amber-300 font-medium uppercase tracking-wider">Research Card</p>
        <span className="ml-auto text-[10px] text-gray-600 mono">{gene.locus}</span>
      </div>

      {/* External tools */}
      <div>
        <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">External tools</p>
        <div className="flex flex-wrap gap-2">
          <a href={esmUrl} target="_blank" rel="noreferrer"
            className="text-xs bg-indigo-600/10 hover:bg-indigo-600/20 border border-indigo-500/20 text-indigo-300 px-3 py-1.5 rounded-lg transition-colors">
            ESMFold structure →
          </a>
          <a href={ncbiUrl} target="_blank" rel="noreferrer"
            className="text-xs bg-white/5 hover:bg-white/8 border border-white/10 text-gray-300 px-3 py-1.5 rounded-lg transition-colors">
            NCBI protein search →
          </a>
          <a href={`https://www.uniprot.org/blast/?about=${encodeURIComponent(gene.locus)}`} target="_blank" rel="noreferrer"
            className="text-xs bg-white/5 hover:bg-white/8 border border-white/10 text-gray-300 px-3 py-1.5 rounded-lg transition-colors">
            UniProt BLAST →
          </a>
        </div>
      </div>

      {/* Primer design hints */}
      {primers && (
        <div>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Primer design hints</p>
          <div className="grid grid-cols-2 gap-2">
            {[
              { label: "Gene length",  value: gene.length ? `${gene.length} bp` : "—" },
              { label: "Strand",       value: gene.strand === -1 ? "Reverse (−)" : "Forward (+)" },
              { label: "GC content",   value: primers.gcHint },
              { label: "Melting temp", value: primers.tmHint },
            ].map(({ label, value }) => (
              <div key={label} className="bg-white/[0.03] border border-white/6 rounded-lg px-3 py-2">
                <p className="text-[10px] text-gray-600 mb-0.5">{label}</p>
                <p className="text-xs text-gray-300 mono">{value}</p>
              </div>
            ))}
          </div>
          {primers.overlapNote && (
            <p className="text-[11px] text-amber-400/70 mt-2">{primers.overlapNote}</p>
          )}
        </div>
      )}

      {/* Suggested experiments */}
      <div>
        <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Suggested experiments</p>
        <div className="space-y-2">
          {EXPERIMENTS.map((exp, i) => (
            <div key={i} className="flex gap-3">
              <span className="w-5 h-5 rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-[9px] font-bold text-amber-400 shrink-0 mt-0.5">
                {i + 1}
              </span>
              <div>
                <p className="text-xs font-medium text-gray-200">{exp.label}</p>
                <p className="text-[11px] text-gray-500 leading-relaxed">{exp.desc}</p>
              </div>
            </div>
          ))}
        </div>
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
