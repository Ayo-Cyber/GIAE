"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ChevronLeft, Download, Share2, Clock, AlertCircle,
  RefreshCw, XCircle, WifiOff, Search, FlaskConical,
  Bookmark, StickyNote,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type { Job, GeneRow } from "@/lib/types";
import { AppNav } from "@/components/nav";
import { ThemeToggle } from "@/components/theme";
import { toGff3, toTsv, toJson, toGenbank, downloadBlob } from "@/lib/export";
import { isBookmarked, toggleBookmark } from "@/lib/bookmarks";
import { getNote, setNote } from "@/lib/notes";
import { cn } from "@/lib/utils";
import {
  ReasoningChain,
  UncertaintyNotes,
  DarkMatterResearchCard,
  CompetingHypothesesChart,
} from "@/components/explainability-panel";
import { GenomeTrack } from "@/components/genome-track";
import { DEMO_JOB_ID, demoJob } from "@/data/demo-data";
import { clusterOperons } from "@/lib/operons";
import type { Operon } from "@/lib/operons";
import { flagGenes } from "@/lib/amr";
import type { BioHit } from "@/lib/amr";

// ── COG category colour map ──────────────────────────────────────────────────
const COG_MAP: Record<string, [string, string]> = {
  A: ["#fb7185", "RNA processing"],
  C: ["#fb923c", "Energy production"],
  D: ["#c084fc", "Cell cycle"],
  E: ["#22d3ee", "Amino-acid transport"],
  F: ["#4ade80", "Nucleotide metabolism"],
  G: ["#facc15", "Carbohydrate"],
  H: ["#c4b5fd", "Coenzyme transport"],
  I: ["#9ca94b", "Lipid metabolism"],
  J: ["#2dd4bf", "Translation"],
  K: ["#6d8bff", "Transcription"],
  L: ["#818cf8", "Replication & repair"],
  M: ["#bd8b5e", "Cell wall/membrane"],
  N: ["#9ca3af", "Cell motility"],
  O: ["#f87171", "Post-translational mod."],
  P: ["#8ca0b3", "Inorganic ion transport"],
  Q: ["#a3e635", "Secondary metabolites"],
  R: ["#cbd5e1", "General prediction"],
  S: ["#6b7280", "Function unknown"],
  T: ["#f472b6", "Signal transduction"],
  U: ["#f97362", "Intracellular trafficking"],
  V: ["#34d399", "Defense mechanisms"],
  X: ["#f59e0b", "Mobilome: prophages, transposons"],
};

function cogColor(l: string | null | undefined) {
  return l ? (COG_MAP[l]?.[0] ?? "#6b7280") : "#6b7280";
}
function cogName(l: string | null | undefined) {
  return l ? (COG_MAP[l]?.[1] ?? "Unknown") : "";
}
function ha(hex: string, a: number) {
  const n = parseInt(hex.replace("#", ""), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}
function confColor(level: string | null | undefined) {
  return ({ HIGH: "#34d399", MODERATE: "#f59e0b", LOW: "#818cf8", SPECULATIVE: "#a78bfa" } as Record<string, string>)[level ?? ""] ?? "#9ca3af";
}

// Empirical reliability ramp for the CALIBRATED probability of correctness.
// Distinct axis from the model's confidence LEVEL (confColor): this answers
// "how much should I actually trust this call?" — green safe → amber verify →
// red hypothesis-only. Colors reuse the palette's existing semantic vocabulary.
function reliabilityColor(p: number) {
  if (p >= 0.65) return "#34d399"; // emerald — dependable
  if (p >= 0.4) return "#f59e0b";  // amber — a lead, verify
  return "#f87171";                // red — hypothesis only
}

function reliabilityVerdict(p: number): { tag: string; note: string } {
  if (p >= 0.65)
    return { tag: "Dependable", note: "High empirical reliability — safe to carry forward." };
  if (p >= 0.4)
    return { tag: "Verify", note: "A credible lead — confirm before relying on it." };
  return { tag: "Hypothesis only", note: "Low reliability — treat as a direction to test, not a conclusion." };
}

function sourceStyle(src: string): { short: string; color: string } {
  const s = src.toLowerCase();
  if (s.includes("pfam") || s.includes("hmmer"))  return { short: "HMMER/Pfam", color: "#34d399" };
  if (s.includes("prosite"))                       return { short: "PROSITE",    color: "#facc15" };
  if (s.includes("uniprot"))                       return { short: "UniProt",    color: "#818cf8" };
  if (s.includes("interpro"))                      return { short: "InterPro",   color: "#a78bfa" };
  if (s.includes("esm"))                           return { short: "ESM-2",      color: "#f472b6" };
  if (s.includes("genbank") || s.includes("card")) return { short: "GenBank",    color: "#22d3ee" };
  return { short: src.split(/[\s/]/)[0].slice(0, 10), color: "#9ca3af" };
}

function evidenceMetric(ev: { source: string; label: string; conf: number }): string {
  const lbl = ev.label ?? "";
  const pctMatch = lbl.match(/(\d+\.?\d*)\s*%/);
  if (pctMatch) return `${pctMatch[1]}% id`;
  const eMatch = lbl.match(/[Ee][- ]([\d.e+-]+)/);
  if (eMatch) return `E ${eMatch[1]}`;
  const src = (ev.source ?? "").toLowerCase();
  if (src.includes("prosite")) return "pattern";
  if (src.includes("genbank") || src.includes("card")) return "curated";
  if (src.includes("pfam") || src.includes("hmmer")) return "profile";
  return "—";
}

function CogChip({ letter, size = "sm" }: { letter?: string | null; size?: "sm" | "lg" }) {
  if (!letter) return null;
  const c = cogColor(letter);
  if (size === "lg") {
    return (
      <span
        title={`${letter} · ${cogName(letter)}`}
        className="inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full border font-medium shrink-0"
        style={{ color: c, backgroundColor: ha(c, 0.12), borderColor: ha(c, 0.3) }}
      >
        <span
          className="inline-flex items-center justify-center font-mono font-bold text-[11px] w-4 h-4 rounded"
          style={{ backgroundColor: c, color: "#0a0a14" }}
        >
          {letter}
        </span>
        {cogName(letter)}
      </span>
    );
  }
  return (
    <span
      title={`${letter} · ${cogName(letter)}`}
      className="inline-flex items-center justify-center font-mono font-bold text-[9px] w-3.5 h-3.5 rounded shrink-0"
      style={{ backgroundColor: ha(c, 0.18), color: c, border: `1px solid ${ha(c, 0.45)}` }}
    >
      {letter}
    </span>
  );
}

// ── Inline: Evidence Ladder ──────────────────────────────────────────────────
function EvidenceLadder({ gene }: { gene: GeneRow }) {
  const ev = gene.evidence ?? [];
  if (ev.length === 0 && !gene.is_dark) return null;
  if (gene.is_dark) {
    return (
      <div className="bg-[#0f0f1e] border border-white/7 rounded-[14px] p-[18px]">
        <div className="flex items-center gap-2 mb-3">
          <span className="w-3 h-3 rounded-full border-2 border-dashed border-gray-600 shrink-0" />
          <span className="text-[11px] text-gray-400 font-semibold uppercase tracking-wider">Evidence ladder</span>
          <span className="ml-auto text-[10px] text-gray-600">no hits recorded</span>
        </div>
        <p className="text-xs text-gray-600">GIAE queried all evidence databases and returned no hits for this locus.</p>
      </div>
    );
  }
  const maxConf = Math.max(...ev.map((e) => e.conf), 0.01);
  const allSources = ["HMMER/Pfam", "PROSITE", "UniProt", "InterPro", "GenBank", "ESM-2"];
  const haveSources = new Set(ev.map((e) => sourceStyle(e.source).short));
  const missing = allSources.filter((s) => !haveSources.has(s));
  return (
    <div className="bg-[#0f0f1e] border border-white/7 rounded-[14px] p-[18px]">
      <div className="flex items-center gap-2 mb-1">
        <span className="w-3 h-3 rounded-full border-2 border-dashed border-cyan-500/60 shrink-0" />
        <span className="text-[11px] text-gray-400 font-semibold uppercase tracking-wider">Evidence ladder</span>
        <span className="ml-auto text-[10px] text-gray-600">bar = confidence · color = source class</span>
      </div>
      <div className="flex flex-col gap-3 mt-4">
        {ev.map((e, i) => {
          const { short, color } = sourceStyle(e.source);
          const pct = Math.round((e.conf / maxConf) * 100);
          const metric = evidenceMetric(e);
          return (
            <div key={i}>
              <div className="flex items-center gap-2.5">
                <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
                <span className="w-24 shrink-0 font-mono text-[11px] font-semibold" style={{ color }}>{short}</span>
                <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.05)" }}>
                  <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
                </div>
                <span className="w-8 text-right shrink-0 font-mono text-[11px] text-gray-400">{e.conf.toFixed(2)}</span>
                <span className="w-20 text-right shrink-0 font-mono text-[10px] text-gray-600">{metric}</span>
              </div>
              <div className="text-[11px] text-gray-600 pl-[26px] mt-0.5 truncate">{e.label}</div>
            </div>
          );
        })}
      </div>
      {missing.length > 0 && (
        <div className="mt-3.5 pt-3 border-t border-white/5">
          <div className="text-[10px] text-gray-700 mb-1.5">No signal from:</div>
          <div className="flex flex-wrap gap-1.5">
            {missing.map((m) => (
              <span key={m} className="text-[10px] font-mono px-2 py-0.5 rounded" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", color: "#4b5563" }}>{m}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Inline: Confidence Donut ─────────────────────────────────────────────────
function ConfidenceDonut({ gene, operon }: { gene: GeneRow; operon?: Operon }) {
  if (gene.is_dark || gene.score == null) return null;
  const score = gene.score;
  const level = gene.confidence ?? "LOW";
  const c = confColor(level);
  const pct = Math.round(score * 100);
  const ev = gene.evidence ?? [];
  const strongest = ev.length ? ev.reduce((a, b) => (b.conf > a.conf ? b : a)) : null;
  const { short: strongShort, color: strongColor } = strongest ? sourceStyle(strongest.source) : { short: "—", color: "#9ca3af" };
  const stats = [
    { label: "Confidence level", value: level, color: c },
    { label: "Evidence sources", value: String(ev.length), color: "#e5e7eb" },
    { label: "Strongest hit", value: strongest ? `${strongShort} ${strongest.conf.toFixed(2)}` : "—", color: strongColor },
    { label: "COG category", value: gene.cog_category ? `${gene.cog_category} · ${cogName(gene.cog_category)}` : "—", color: cogColor(gene.cog_category) },
  ];
  return (
    <div className="bg-[#0f0f1e] border border-white/7 rounded-[14px] p-[18px]">
      <div className="text-[11px] text-gray-400 font-semibold uppercase tracking-wider mb-4">Confidence</div>
      <div className="flex items-center gap-4">
        <div
          className="w-[100px] h-[100px] rounded-full shrink-0 flex items-center justify-center"
          style={{
            background: `conic-gradient(from -90deg, ${c} 0% ${pct}%, var(--divider) ${pct}% 100%)`,
          }}
        >
          <div className="w-[72px] h-[72px] rounded-full bg-[#0f0f1e] flex flex-col items-center justify-center">
            <span className="text-xl font-bold font-mono leading-none" style={{ color: c }}>{score.toFixed(2)}</span>
            <span className="text-[9px] uppercase tracking-widest text-gray-600 mt-0.5">{level}</span>
          </div>
        </div>
        <div className="flex-1 flex flex-col gap-2.5 min-w-0">
          {stats.map((s) => (
            <div key={s.label} className="flex flex-col gap-0.5">
              <span className="text-[10px] text-gray-600">{s.label}</span>
              <span className="text-xs font-mono truncate" style={{ color: s.color }}>{s.value}</span>
            </div>
          ))}
        </div>
      </div>
      <CalibratedReliability gene={gene} />
    </div>
  );
}

// ── Calibrated reliability ───────────────────────────────────────────────────
// The model's raw confidence is over-confident (benchmarked: mean 0.83 vs 0.54
// accuracy). When a homology hit backs the call, GIAE reports a cross-validated,
// calibrated probability of correctness. We show it on the SAME 0–100 scale as
// the raw score with the raw value marked, so the researcher sees the model's
// self-assessment shrink to its empirical reliability.
function CalibratedReliability({ gene }: { gene: GeneRow }) {
  const cal = gene.calibrated_confidence;
  if (cal == null) return null;
  const raw = gene.score ?? cal;
  const calPct = Math.round(cal * 100);
  const rawPct = Math.round(raw * 100);
  const rc = reliabilityColor(cal);
  const { tag, note } = reliabilityVerdict(cal);
  const shrinks = rawPct - calPct >= 3;

  return (
    <div className="mt-4 pt-4 border-t" style={{ borderColor: "var(--divider)" }}>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-[11px] text-gray-400 font-semibold uppercase tracking-wider">
          Calibrated reliability
        </span>
        <span
          className="text-[10px] font-medium px-1.5 py-0.5 rounded"
          style={{ color: rc, backgroundColor: ha(rc, 0.13), border: `1px solid ${ha(rc, 0.3)}` }}
        >
          {tag}
        </span>
        {gene.calibration_model && (
          <span
            className="ml-auto text-[9px] font-mono text-gray-600 truncate"
            title={`Calibration model: ${gene.calibration_model}`}
          >
            {gene.calibration_model}
          </span>
        )}
      </div>

      {/* meter: calibrated fill + raw-score marker on one 0–100 scale */}
      <div className="flex items-baseline gap-2 mb-1.5">
        <span className="text-2xl font-bold font-mono leading-none" style={{ color: rc }}>
          {calPct}%
        </span>
        <span className="text-[11px] text-gray-500">P(matches curated product)</span>
      </div>
      <div
        className="relative h-2.5 rounded-full overflow-visible"
        style={{ background: "var(--divider)" }}
        role="meter"
        aria-valuenow={calPct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Calibrated probability of correctness"
      >
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ width: `${calPct}%`, background: rc }}
        />
        {shrinks && (
          <span
            className="absolute top-1/2 -translate-y-1/2 h-4 w-[2px] rounded"
            style={{ left: `calc(${rawPct}% - 1px)`, background: "var(--fg-faint, #9ca3af)", opacity: 0.7 }}
            title={`Raw model confidence ${raw.toFixed(2)}`}
          />
        )}
      </div>

      {shrinks && (
        <p className="text-[10.5px] text-gray-600 mt-2 font-mono">
          model said <span className="text-gray-400">{raw.toFixed(2)}</span>
          <span className="mx-1">→</span>
          calibrated <span style={{ color: rc }}>{cal.toFixed(2)}</span>
          <span className="text-gray-700"> · marker = raw</span>
        </p>
      )}
      <p className="text-[11px] text-gray-500 mt-2 leading-relaxed">
        {note} Out-of-sample probability this annotation matches a curated RefSeq
        product name — conservative, since synonymous names aren&apos;t credited.
      </p>
    </div>
  );
}

// ── Domain architecture + amino-acid sequence viewer ─────────────────────────
function DomainSequenceCard({ gene }: { gene: GeneRow }) {
  const seq = gene.aa_sequence;
  if (!seq) return null;
  const len = gene.aa_length ?? seq.length;
  const domains = (gene.domains ?? []).filter((d) => d.end > d.start);

  // Per-residue color from the first covering domain → merged into segments.
  const colorAt: (string | null)[] = new Array(seq.length).fill(null);
  for (const d of domains) {
    const c = sourceStyle(d.source).color;
    for (let i = Math.max(0, d.start); i < Math.min(seq.length, d.end); i++) {
      if (!colorAt[i]) colorAt[i] = c;
    }
  }
  const segs: { color: string | null; text: string }[] = [];
  for (let i = 0; i < seq.length; i++) {
    const c = colorAt[i];
    const last = segs[segs.length - 1];
    if (!last || last.color !== c) segs.push({ color: c, text: seq[i] });
    else last.text += seq[i];
  }

  // Legend: unique sources present in the domain blocks.
  const legend = Array.from(new Set(domains.map((d) => d.source))).map((s) => ({
    label: sourceStyle(s).short,
    color: sourceStyle(s).color,
  }));

  return (
    <div className="bg-[#0f0f1e] border border-white/7 rounded-[14px] p-[18px]">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-[11px] text-gray-400 font-semibold uppercase tracking-wider">Domain architecture</span>
        <span className="ml-auto text-[10px] font-mono text-gray-600">{len} aa</span>
      </div>

      {domains.length > 0 ? (
        <>
          {/* track */}
          <div className="relative h-[54px] my-4">
            <div className="absolute left-0 right-0 top-6 h-1.5 rounded-full" style={{ background: "var(--divider)" }} />
            {domains.map((d, i) => {
              const left = (d.start / len) * 100;
              const width = Math.max(((d.end - d.start) / len) * 100, 0.6);
              const c = sourceStyle(d.source).color;
              return (
                <div key={i}>
                  <div
                    title={d.label}
                    className="absolute top-[18px] h-3.5 rounded"
                    style={{ left: `${left}%`, width: `${width}%`, minWidth: 3, background: ha(c, 0.22), border: `1px solid ${ha(c, 0.55)}` }}
                  />
                  {width > 8 && (
                    <div className="absolute top-1 text-[9px] font-mono whitespace-nowrap overflow-hidden"
                      style={{ left: `${left}%`, maxWidth: `${width}%`, color: c }}>
                      {sourceStyle(d.source).short}
                    </div>
                  )}
                </div>
              );
            })}
            <span className="absolute left-0 bottom-0 text-[9px] font-mono text-gray-600">1</span>
            <span className="absolute right-0 bottom-0 text-[9px] font-mono text-gray-600">{len}</span>
          </div>
          {/* legend */}
          <div className="flex flex-wrap gap-3 mb-3.5 pt-3 border-t border-white/5">
            {legend.map((l) => (
              <span key={l.label} className="flex items-center gap-1.5 text-[10px] text-gray-400">
                <span className="w-2.5 h-2.5 rounded" style={{ background: ha(l.color, 0.22), border: `1px solid ${ha(l.color, 0.55)}` }} />
                {l.label}
              </span>
            ))}
          </div>
        </>
      ) : (
        <div className="text-[11px] text-gray-600 my-3">No positional domain or motif hits — sequence shown below.</div>
      )}

      <div className="text-[10px] text-gray-600 uppercase tracking-wider mb-2">
        Amino-acid sequence{domains.length > 0 ? " · motifs highlighted" : ""}
      </div>
      <div className="font-mono text-[11px] leading-[1.85] tracking-[1.5px] break-all max-h-[150px] overflow-y-auto bg-[#0a0a14] border border-white/5 rounded-[9px] px-3 py-2.5">
        {segs.map((s, i) => (
          <span key={i} style={s.color ? { background: ha(s.color, 0.2), color: s.color, borderRadius: 2 } : { color: "#9ca3af" }}>
            {s.text}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Type ─────────────────────────────────────────────────────────────────────
type GeneFilter = "all" | "high" | "moderate" | "low" | "dark" | "amr" | "virulence";

const FILTER_TABS: { key: GeneFilter; label: string; color?: string }[] = [
  { key: "all",       label: "All"  },
  { key: "high",      label: "High" },
  { key: "moderate",  label: "Mod"  },
  { key: "low",       label: "Low"  },
  { key: "dark",      label: "Dark" },
  { key: "amr",       label: "AMR",  color: "#f87171" },
  { key: "virulence", label: "Vir",  color: "#fb923c" },
];

export default function JobPage() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob]           = useState<Job | null>(null);
  const [selected, setSelected] = useState<GeneRow | null>(null);
  const [filter, setFilter]     = useState<GeneFilter>("all");
  const [cogFilter, setCogFilter] = useState<string | null>(null);
  const [query, setQuery]       = useState("");
  const [rerunning, setRerunning]   = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [copied, setCopied]         = useState(false);
  const [workerOnline, setWorkerOnline] = useState<boolean | null>(null);
  const [exportOpen, setExportOpen]     = useState(false);
  const [bookmarked, setBookmarked]     = useState(false);
  const [note, setNoteState]            = useState("");
  const [watched, setWatched]           = useState(false);
  const [historyDiff, setHistoryDiff]   = useState<{ previous: GeneRow[]; current: GeneRow[] } | null>(null);
  const [showHistory, setShowHistory]   = useState(false);
  const isDemo = id === DEMO_JOB_ID;

  useEffect(() => {
    if (isDemo) { setJob(demoJob); setSelected(demoJob.genes[0]); return; }
    api.getJob(id).then((j) => { setJob(j); if (j.genes?.length > 0) setSelected(j.genes[0]); });
    const stop = api.pollJob(id, (j) => {
      setJob(j);
      if (j.genes?.length > 0 && !selected) setSelected(j.genes[0]);
    });
    return stop;
  }, [id, isDemo]);

  useEffect(() => {
    if (job?.status !== "PENDING" && job?.status !== "RUNNING") return;
    api.workerStatus().then((s) => setWorkerOnline(s.online)).catch(() => setWorkerOnline(false));
  }, [job?.status]);

  useEffect(() => {
    if (!selected) return;
    setBookmarked(isBookmarked(selected.id));
    setNoteState(getNote(id, selected.id));
    if (selected.is_dark) {
      api.getWatchlist()
        .then((entries) => setWatched(entries.some((e) => e.locus === selected.locus)))
        .catch(() => {});
    } else {
      setWatched(false);
    }
  }, [selected?.id, id]);

  useEffect(() => {
    if (isDemo || job?.status !== "COMPLETED") return;
    api.getJobHistory(id)
      .then((h) => setHistoryDiff({ previous: h.previous_genes, current: h.current_genes }))
      .catch(() => {});
  }, [isDemo, job?.status, id]);

  const isRunning    = job?.status === "RUNNING" || job?.status === "PENDING";
  const isCancellable = job?.status === "PENDING"  || job?.status === "RUNNING";

  const { operons, geneToOperon } = useMemo(
    () => clusterOperons(job?.genes ?? []),
    [job?.genes]
  );
  const selectedOperon: Operon | undefined = selected ? geneToOperon.get(selected.id) : undefined;

  const amrFlags: Map<string, BioHit[]> = useMemo(
    () => flagGenes(job?.genes ?? []),
    [job?.genes]
  );
  const selectedFlags: BioHit[] = selected ? (amrFlags.get(selected.id) ?? []) : [];
  const amrCount       = amrFlags.size;
  const virulenceCount = Array.from(amrFlags.values()).filter((hits) => hits.some((h: BioHit) => h.type === "virulence")).length;

  const cogLetters = useMemo(() => {
    const letters = Array.from(new Set((job?.genes ?? []).map((g) => g.cog_category).filter(Boolean))) as string[];
    return letters.sort();
  }, [job?.genes]);

  const genes = (job?.genes ?? []).filter((g) => {
    if (filter === "high"     && !(g.confidence === "HIGH" && !g.is_dark)) return false;
    if (filter === "moderate" && !(g.confidence === "MODERATE" && !g.is_dark)) return false;
    if (filter === "low"      && !((g.confidence === "LOW" || g.confidence === "SPECULATIVE") && !g.is_dark)) return false;
    if (filter === "dark"      && !g.is_dark) return false;
    if (filter === "amr"       && !amrFlags.has(g.id)) return false;
    if (filter === "virulence" && !(amrFlags.get(g.id) ?? []).some((h) => h.type === "virulence")) return false;
    if (cogFilter && g.cog_category !== cogFilter) return false;
    if (query.trim()) {
      const q   = query.trim().toLowerCase();
      const hay = `${g.name} ${g.locus} ${g.function ?? ""} ${g.normalized_product ?? ""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  const successRate = job?.total_genes && job.total_genes > 0
    ? Math.round(((job.interpreted_genes ?? 0) / job.total_genes) * 100)
    : 0;

  return (
    <div className="h-screen overflow-hidden bg-[#0a0a14] flex">
      <AppNav />

      <div className="app-shell flex flex-col flex-1 min-w-0 h-screen overflow-hidden">

        {/* ── Toolbar ───────────────────────────────────────────────── */}
        <div className="shrink-0 h-13 border-b border-white/5 flex items-center gap-3 px-4 bg-[#0a0a14]" style={{ height: 52 }}>
          <Link href="/dashboard" className="text-gray-500 hover:text-gray-300 transition-colors">
            <ChevronLeft size={15} />
          </Link>

          {/* GIAE logo badge */}
          <div className="w-6 h-6 rounded-md flex items-center justify-center font-bold text-[11px] text-white shrink-0"
            style={{ background: "linear-gradient(135deg,#6366f1,#818cf8)" }}>
            G
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <p className="text-[13px] font-semibold text-white font-mono truncate">{job?.filename ?? id}</p>
              {isDemo && (
                <span className="inline-flex items-center gap-1 text-[10px] text-cyan-200 bg-cyan-400/10 border border-cyan-400/20 px-1.5 py-0.5 rounded-full shrink-0">
                  <FlaskConical size={9} /> sample · λ
                </span>
              )}
            </div>
            <p className="text-[11px] text-gray-500 font-mono">
              {job?.total_genes != null
                ? `${job.total_genes} features · ${job.processing_time_seconds ?? "—"}s`
                : "Loading…"}
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <ThemeToggle />

            {job?.status === "COMPLETED" && (
              <button
                onClick={async () => {
                  try {
                    const { token } = await api.shareJob(id);
                    const url = `${window.location.origin}/report/${token}`;
                    await navigator.clipboard.writeText(url);
                    setCopied(true);
                    setTimeout(() => setCopied(false), 2000);
                    toast.success("Share link copied to clipboard.");
                  } catch {
                    toast.error("Could not generate share link.");
                  }
                }}
                className="flex items-center gap-1.5 text-xs bg-white/4 hover:bg-white/8 border border-white/10 px-2.5 py-1.5 rounded-lg text-gray-400 transition-colors"
              >
                <Share2 size={11} /> {copied ? "Copied!" : "Share"}
              </button>
            )}

            {job?.status === "COMPLETED" && (
              <div className="relative">
                <button
                  onClick={() => setExportOpen((v) => !v)}
                  className="flex items-center gap-1.5 text-xs bg-white/4 hover:bg-white/8 border border-white/10 px-2.5 py-1.5 rounded-lg text-gray-400 transition-colors"
                >
                  <Download size={11} /> Export
                </button>
                {exportOpen && (
                  <>
                    <div className="fixed inset-0 z-30" onClick={() => setExportOpen(false)} />
                    <div className="absolute right-0 top-8 z-40 bg-[#0f0f1e] border border-white/10 rounded-xl shadow-xl p-1.5 w-44">
                      {[
                        { label: "GFF3", ext: "gff3", mime: "text/plain",       fn: () => toGff3(job!)    },
                        { label: "TSV",  ext: "tsv",  mime: "text/tab-separated-values", fn: () => toTsv(job!) },
                        { label: "JSON", ext: "json", mime: "application/json", fn: () => toJson(job!)    },
                        { label: "GenBank (simplified)", ext: "gbk", mime: "text/plain", fn: () => toGenbank(job!) },
                      ].map(({ label, ext, mime, fn }) => (
                        <button
                          key={ext}
                          onClick={() => {
                            const base = job!.filename.replace(/\.[^.]+$/, "");
                            downloadBlob(fn(), `${base}.giae.${ext}`, mime);
                            setExportOpen(false);
                            toast.success(`Downloaded ${base}.giae.${ext}`);
                          }}
                          className="w-full flex items-center gap-2.5 text-xs text-gray-300 hover:text-white hover:bg-white/6 rounded-lg px-3 py-2 transition-colors text-left"
                        >
                          <Download size={11} className="text-gray-500 shrink-0" />
                          {label}
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}

            {isCancellable && (
              <button
                onClick={async () => {
                  setCancelling(true);
                  try { await api.cancelJob(id); const j = await api.getJob(id); setJob(j); toast.success("Job cancelled."); }
                  catch { toast.error("Failed to cancel job."); }
                  finally { setCancelling(false); }
                }}
                disabled={cancelling}
                className="flex items-center gap-1.5 text-xs bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 px-2.5 py-1.5 rounded-lg text-red-400 transition-colors disabled:opacity-50"
              >
                <XCircle size={11} className={cancelling ? "animate-spin" : ""} />
                {cancelling ? "Cancelling…" : "Cancel"}
              </button>
            )}

            {!isDemo && (job?.status === "COMPLETED" || job?.status === "FAILED") && (
              <button
                onClick={async () => {
                  setRerunning(true);
                  try { await api.rerunJob(id); const j = await api.getJob(id); setJob(j); setSelected(null); toast.success("Job queued for re-run."); }
                  catch { toast.error("Failed to re-run job."); }
                  finally { setRerunning(false); }
                }}
                disabled={rerunning}
                className="flex items-center gap-1.5 text-xs bg-white/4 hover:bg-white/8 border border-white/10 px-2.5 py-1.5 rounded-lg text-gray-400 transition-colors disabled:opacity-50"
              >
                <RefreshCw size={11} className={rerunning ? "animate-spin" : ""} /> Re-run
              </button>
            )}

            {job?.report_url && (
              <a href={job.report_url} target="_blank"
                className="flex items-center gap-1.5 text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-2.5 py-1.5 rounded-lg font-medium transition-colors">
                <Download size={11} /> Report
              </a>
            )}
          </div>
        </div>

        {/* ── Worker offline banner ──────────────────────────────────── */}
        {isRunning && workerOnline === false && (
          <div className="shrink-0 mx-4 mt-3 flex items-center gap-3 bg-amber-500/10 border border-amber-500/20 rounded-xl px-4 py-2.5">
            <WifiOff size={14} className="text-amber-400 shrink-0" />
            <p className="text-xs text-amber-300">
              Worker not running — start it with{" "}
              <span className="font-mono bg-amber-500/10 px-1 rounded">make worker</span>
            </p>
          </div>
        )}

        {/* ── Loading skeleton ───────────────────────────────────────── */}
        {!job && !isDemo && (
          <div className="flex flex-1 overflow-hidden">
            <div className="w-[290px] border-r border-white/5 p-3 space-y-2">
              {[0,1,2,3,4,5].map((i) => (
                <div key={i} className="h-14 bg-white/4 rounded-lg animate-pulse" style={{ opacity: 1 - i * 0.1 }} />
              ))}
            </div>
            <div className="flex-1 p-6 space-y-4">
              <div className="h-28 bg-white/4 rounded-xl animate-pulse" />
              <div className="grid grid-cols-4 gap-3">
                {[1,2,3,4].map((i) => <div key={i} className="h-16 bg-white/4 rounded-xl animate-pulse" />)}
              </div>
              <div className="h-48 bg-white/4 rounded-xl animate-pulse" />
            </div>
          </div>
        )}

        {/* ── Running ───────────────────────────────────────────────── */}
        {isRunning && (
          <div className="flex flex-col items-center justify-center flex-1 px-6 py-20 text-center">
            <div className="w-16 h-16 rounded-2xl bg-indigo-600/15 border border-indigo-500/25 flex items-center justify-center mb-6 relative">
              <Clock size={26} className="text-indigo-400 animate-spin" />
              <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-emerald-400 animate-pulse" />
            </div>
            <h2 className="text-lg font-semibold text-white mb-2">Interpreting genome…</h2>
            <p className="text-gray-400 text-sm mb-6">{job?.filename}</p>
            <p className="text-xs text-gray-500 font-mono">
              {job?.status === "PENDING" ? "Queued — waiting for worker" : "Running GIAE pipeline…"}
            </p>
          </div>
        )}

        {/* ── Cancelled ─────────────────────────────────────────────── */}
        {job?.status === "CANCELLED" && (
          <div className="flex flex-col items-center justify-center flex-1 text-center">
            <XCircle size={32} className="text-gray-500 mb-4" />
            <h2 className="text-lg font-semibold text-white mb-2">Job cancelled</h2>
            <p className="text-sm text-gray-400">This job was cancelled before it completed.</p>
          </div>
        )}

        {/* ── Failed ────────────────────────────────────────────────── */}
        {job?.status === "FAILED" && (
          <div className="flex flex-col items-center justify-center flex-1 text-center">
            <AlertCircle size={32} className="text-red-400 mb-4" />
            <h2 className="text-lg font-semibold text-white mb-2">Job failed</h2>
            <p className="text-sm text-gray-400">{job.error_message ?? "Unknown error"}</p>
          </div>
        )}

        {/* ── Completed ─────────────────────────────────────────────── */}
        {job?.status === "COMPLETED" && (
          <div className="flex flex-1 overflow-hidden">

            {/* ── Left pane: gene list ────────────────────────────── */}
            <div className="w-[290px] shrink-0 border-r border-white/5 flex flex-col overflow-hidden bg-[#0b0b16]">

              {/* Search + filter tabs + COG chips */}
              <div className="p-2.5 border-b border-white/5 space-y-2">
                <div className="relative">
                  <Search size={11} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-600 pointer-events-none" />
                  <input
                    type="text" value={query} onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search genes, loci, products…"
                    className="w-full text-xs bg-white/4 border border-white/8 rounded-md pl-7 pr-2 py-1.5 text-gray-200 placeholder-gray-600 outline-none focus:border-indigo-500/40 transition-colors font-mono"
                  />
                </div>

                {/* Filter tabs */}
                <div className="flex gap-1">
                  {FILTER_TABS.map(({ key, label, color }) => {
                    const count = key === "amr" ? amrCount : key === "virulence" ? virulenceCount : null;
                    const active = filter === key;
                    return (
                      <button key={key} onClick={() => setFilter(key)}
                        className="flex-1 text-[10px] font-mono font-semibold py-1 rounded-md transition-colors flex items-center justify-center gap-0.5"
                        style={{
                          background: active ? (color ? ha(color, 0.16) : "rgba(99,102,241,0.18)") : "transparent",
                          color: active ? (color ?? "#a5b4fc") : "#6b7280",
                          border: `1px solid ${active ? (color ? ha(color, 0.4) : "rgba(99,102,241,0.35)") : "transparent"}`,
                        }}
                      >
                        {label}
                        {count !== null && count > 0 && (
                          <span className="opacity-60 text-[9px]">{count}</span>
                        )}
                      </button>
                    );
                  })}
                </div>

                {/* COG letter chips */}
                {cogLetters.length > 0 && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-[9px] text-gray-600 uppercase tracking-wider shrink-0">COG</span>
                    <div className="flex gap-1 flex-wrap">
                      {cogLetters.map((l) => {
                        const c = cogColor(l);
                        const active = cogFilter === l;
                        return (
                          <button
                            key={l}
                            onClick={() => setCogFilter(cogFilter === l ? null : l)}
                            title={`${l} · ${cogName(l)}`}
                            className="font-mono text-[10px] font-bold w-[18px] h-[18px] flex items-center justify-center rounded cursor-pointer transition-all"
                            style={{
                              background: active ? c : ha(c, 0.16),
                              color: active ? "#0a0a14" : c,
                              border: `1px solid ${active ? c : ha(c, 0.4)}`,
                            }}
                          >
                            {l}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                <p className="text-[10px] text-gray-600 font-mono">
                  {genes.length} / {job.total_genes ?? 0} features
                </p>
              </div>

              {/* Gene rows */}
              <div className="flex-1 overflow-y-auto p-1.5">
                {genes.length === 0 ? (
                  <div className="px-2 py-8 text-center">
                    <p className="text-xs text-gray-600">No matches</p>
                    {(filter !== "all" || query || cogFilter) && (
                      <button onClick={() => { setFilter("all"); setQuery(""); setCogFilter(null); }}
                        className="text-[11px] text-indigo-400 hover:text-indigo-300 mt-1.5">
                        Clear filters
                      </button>
                    )}
                  </div>
                ) : (() => {
                  const rows: React.ReactNode[] = [];
                  let prevOpId: number | null = null;
                  genes.forEach((g) => {
                    const isSel  = selected?.id === g.id;
                    const op     = geneToOperon.get(g.id);
                    const gFlags = amrFlags.get(g.id) ?? [];
                    const hasAmr = gFlags.some((h: BioHit) => h.type === "amr");
                    const hasVir = gFlags.some((h: BioHit) => h.type === "virulence");
                    const stripCol = g.is_dark ? "#b45309"
                      : g.confidence === "HIGH"     ? "#34d399"
                      : g.confidence === "MODERATE" ? "#f59e0b"
                      : "#818cf8";

                    // Operon group header
                    if (op && op.id !== prevOpId) {
                      prevOpId = op.id;
                      rows.push(
                        <div key={`op-header-${op.id}`} className="flex items-center gap-1.5 px-2 pt-2 pb-0.5">
                          <span className="w-2 h-px rounded" style={{ background: op.color }} />
                          <span className="text-[9px] font-bold uppercase tracking-wider" style={{ color: op.color }}>
                            {op.label} operon
                          </span>
                          <span className="flex-1 h-px" style={{ background: `linear-gradient(90deg, ${op.color}, transparent)` }} />
                        </div>
                      );
                    } else if (!op) {
                      prevOpId = null;
                    }

                    rows.push(
                      <button key={g.id} onClick={() => setSelected(g)}
                        className={cn(
                          "group w-full text-left pl-2 pr-2.5 py-2 rounded-lg transition-all relative overflow-hidden mb-px",
                          isSel ? "bg-indigo-600/13 ring-1 ring-indigo-500/30" : op ? "hover:bg-white/[0.04]" : "hover:bg-white/5"
                        )}
                        style={op && !isSel ? { background: ha(op.color, 0.04) } : undefined}
                      >
                        <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r" style={{ background: stripCol }} />
                        <div className="pl-2">
                          <div className="flex items-center justify-between gap-2 mb-0.5">
                            <div className="flex items-center gap-1.5 min-w-0">
                              <span className={cn("font-mono text-xs font-semibold truncate", isSel ? "text-white" : "text-gray-200")}>
                                {g.name}
                              </span>
                              <CogChip letter={g.cog_category} />
                            </div>
                            <div className="flex items-center gap-1 shrink-0">
                              {hasAmr && (
                                <span className="text-[9px] px-1 py-0.5 rounded font-bold leading-none" style={{ background: "rgba(239,68,68,0.14)", color: "#f87171", border: "1px solid rgba(239,68,68,0.3)" }}>AMR</span>
                              )}
                              {hasVir && (
                                <span className="text-[9px] px-1 py-0.5 rounded font-bold leading-none" style={{ background: "rgba(249,115,22,0.14)", color: "#fb923c", border: "1px solid rgba(249,115,22,0.3)" }}>VIR</span>
                              )}
                              {op && (
                                <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: op.color }} />
                              )}
                              {g.length != null && (
                                <span className="text-[10px] font-mono text-gray-600">
                                  {g.length < 1000 ? `${g.length}b` : `${(g.length / 1000).toFixed(1)}k`}
                                </span>
                              )}
                            </div>
                          </div>
                          <p className="text-[11px] text-gray-500 truncate leading-tight">
                            {g.normalized_product ?? g.function ?? (g.is_dark ? "Dark matter — uncharacterized" : "Hypothetical protein")}
                          </p>
                          <p className="text-[10px] text-gray-700 font-mono mt-0.5 truncate">{g.locus}</p>
                        </div>
                      </button>
                    );
                  });
                  return rows;
                })()}
              </div>
            </div>

            {/* ── Right area ──────────────────────────────────────── */}
            <div className="flex-1 overflow-hidden flex flex-col min-w-0">

              {/* Genome track */}
              <div className="shrink-0 border-b border-white/5 px-4 py-3 bg-[#0a0a14]">
                <div className="bg-[#0f0f1e] border border-white/6 rounded-xl overflow-hidden">
                  <div className="flex items-center justify-between gap-4 px-4 pt-3 pb-1">
                    <div>
                      <div className="text-[11px] text-gray-400 font-semibold uppercase tracking-wider">
                        Genome map{job.filename ? ` · ` : ""}<span className="text-gray-600">{job.filename}</span>
                      </div>
                      <div className="text-[11px] text-gray-600 mt-0.5">Forward strand above · reverse below · click a gene to inspect</div>
                    </div>
                    <div className="flex items-center gap-2.5 flex-wrap justify-end shrink-0">
                      {[
                        { c: "#34d399", l: "HIGH" }, { c: "#f59e0b", l: "MOD" },
                        { c: "#818cf8", l: "LOW"  }, { c: "#4b5563", l: "DARK", dashed: true },
                        { c: "#ef4444", l: "AMR"  }, { c: "#f97316", l: "VIR"  },
                      ].map(({ c, l, dashed }) => (
                        <span key={l} className="flex items-center gap-1 text-[10px] text-gray-600">
                          <span className="w-2 h-2 rounded-sm shrink-0" style={{ background: c, border: dashed ? `1px dashed #6b7280` : "none" }} />
                          {l}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="px-4 pb-3">
                    <GenomeTrack
                      genes={job.genes ?? []}
                      selectedId={selected?.id ?? null}
                      onSelect={setSelected}
                      operons={operons}
                      geneToOperon={geneToOperon}
                    />
                  </div>
                </div>
              </div>

              {/* Stats bar */}
              <div className="shrink-0 flex items-center gap-6 px-5 py-2.5 border-b border-white/5 bg-[#0a0a14]">
                {[
                  { v: String(job.total_genes ?? 0),           label: "features",    c: "#ffffff"  },
                  { v: String(job.high_confidence_count ?? 0), label: "high conf",   c: "#34d399"  },
                  { v: String(job.dark_count ?? 0),            label: "dark matter", c: "#f59e0b"  },
                  { v: `${successRate}%`,                      label: "interpreted", c: "#818cf8"  },
                ].map((s) => (
                  <div key={s.label} className="flex items-baseline gap-1.5">
                    <span className="text-lg font-bold font-mono" style={{ color: s.c }}>{s.v}</span>
                    <span className="text-[11px] text-gray-500">{s.label}</span>
                  </div>
                ))}

                {job.total_genes && job.total_genes > 0 && (() => {
                  const all  = job.genes ?? [];
                  const high = all.filter((g) => g.confidence === "HIGH" && !g.is_dark).length;
                  const mod  = all.filter((g) => g.confidence === "MODERATE" && !g.is_dark).length;
                  const low  = all.filter((g) => (g.confidence === "LOW" || g.confidence === "SPECULATIVE") && !g.is_dark).length;
                  const dark = all.filter((g) => g.is_dark).length;
                  const t    = job.total_genes;
                  return (
                    <div className="flex-1 flex items-center min-w-0 ml-2">
                      <div className="flex-1 flex rounded-full overflow-hidden h-1.5 bg-white/4">
                        {[
                          { n: high, c: "#34d399" }, { n: mod, c: "#f59e0b" },
                          { n: low,  c: "#818cf8" }, { n: dark, c: "#b45309" },
                        ].map((s, i) => s.n > 0 ? (
                          <div key={i} style={{ width: `${(s.n / t) * 100}%`, background: s.c }} />
                        ) : null)}
                      </div>
                    </div>
                  );
                })()}
              </div>

              {/* Phage safety screen */}
              {job.safety && (() => {
                const sf = job.safety;
                const V = {
                  not_recommended: { c: "#ef4444", bg: "rgba(239,68,68,0.08)", bd: "rgba(239,68,68,0.28)", label: "Not recommended" },
                  caution:         { c: "#f59e0b", bg: "rgba(245,158,11,0.08)", bd: "rgba(245,158,11,0.28)", label: "Caution" },
                  no_flags:        { c: "#34d399", bg: "rgba(52,211,153,0.07)", bd: "rgba(52,211,153,0.24)", label: "No red flags" },
                }[sf.verdict] ?? { c: "#818cf8", bg: "rgba(129,140,248,0.07)", bd: "rgba(129,140,248,0.24)", label: sf.verdict };
                const catLabel: Record<string, string> = { lysogeny: "lysogeny", amr: "AMR", virulence: "virulence/toxin" };
                return (
                  <div className="shrink-0 border-b border-white/5 px-5 py-3" style={{ background: V.bg }}>
                    <div className="flex items-center gap-3 flex-wrap">
                      <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-1 rounded-md font-bold"
                        style={{ color: V.c, background: "rgba(0,0,0,0.15)", border: `1px solid ${V.bd}` }}>
                        Phage safety · {V.label}
                      </span>
                      {(["lysogeny", "amr", "virulence"] as const).map((cat) =>
                        sf.counts[cat] > 0 ? (
                          <span key={cat} className="text-[11px] font-mono px-2 py-0.5 rounded-full"
                            style={{ color: V.c, border: `1px solid ${V.bd}` }}>
                            {sf.counts[cat]} {catLabel[cat]}
                          </span>
                        ) : null
                      )}
                      <span className="text-xs text-gray-400 flex-1 min-w-[240px]">{sf.recommendation}</span>
                    </div>
                    {sf.flags.length > 0 && (
                      <details className="mt-2">
                        <summary className="text-[11px] cursor-pointer select-none" style={{ color: V.c }}>
                          {sf.flags.length} flagged {sf.flags.length === 1 ? "gene" : "genes"} — show
                        </summary>
                        <div className="mt-2 flex flex-col gap-1">
                          {sf.flags.map((f, i) => (
                            <div key={i} className="flex items-center gap-2 text-[11px] font-mono">
                              <span className="px-1.5 py-0.5 rounded" style={{ color: f.severity === "critical" ? "#ef4444" : "#f59e0b", background: "rgba(0,0,0,0.15)" }}>
                                {catLabel[f.category]}
                              </span>
                              <span className="text-gray-300">{f.gene_name}</span>
                              <span className="text-gray-500">{f.signal}</span>
                              <span className="text-gray-600 truncate">· {f.product}</span>
                            </div>
                          ))}
                        </div>
                        <p className="text-[10px] text-gray-600 mt-2">Signature screen — flags candidates for expert review, not a validated assay. Absence of a flag is not proof of safety.</p>
                      </details>
                    )}
                  </div>
                );
              })()}

              {/* History diff banner */}
              {historyDiff && (
                <div className="shrink-0 border-b border-white/5 px-5 py-2 bg-indigo-500/5 flex items-center gap-3">
                  <span className="text-xs text-indigo-300">Previous run available —</span>
                  <button
                    onClick={() => setShowHistory((v) => !v)}
                    className="text-xs text-indigo-400 hover:text-indigo-300 underline underline-offset-2 transition-colors"
                  >
                    {showHistory ? "Hide diff" : "Show what changed"}
                  </button>
                </div>
              )}

              {/* History diff table */}
              {historyDiff && showHistory && (() => {
                const prevMap = historyDiff.previous.reduce<Record<string, GeneRow>>(
                  (m, g) => { m[g.locus] = g; return m; }, {}
                );
                const changed = historyDiff.current.filter((g) => {
                  const p = prevMap[g.locus];
                  return p && (p.confidence !== g.confidence || p.is_dark !== g.is_dark);
                });
                const newGenes = historyDiff.current.filter((g) => !prevMap[g.locus]);
                return (
                  <div className="shrink-0 border-b border-white/5 bg-[#0c0c18]">
                    <div className="px-5 py-3 space-y-1 max-h-40 overflow-y-auto">
                      {changed.length === 0 && newGenes.length === 0 ? (
                        <p className="text-xs text-gray-500">No annotation changes detected.</p>
                      ) : (
                        <>
                          {changed.map((g) => {
                            const p = prevMap[g.locus];
                            return (
                              <div key={g.locus} className="flex items-center gap-3 text-xs">
                                <span className="text-gray-400 truncate flex-1">{g.name}</span>
                                <span className="font-mono text-gray-600">{p?.is_dark ? "dark" : p?.confidence ?? "—"}</span>
                                <span className="text-gray-600">→</span>
                                <span className={cn("font-mono", g.is_dark ? "text-amber-400" : g.confidence === "HIGH" ? "text-emerald-400" : "text-indigo-400")}>
                                  {g.is_dark ? "dark" : g.confidence ?? "—"}
                                </span>
                              </div>
                            );
                          })}
                          {newGenes.slice(0, 5).map((g) => (
                            <div key={g.locus} className="flex items-center gap-3 text-xs">
                              <span className="text-gray-400 truncate flex-1">{g.name}</span>
                              <span className="text-emerald-400 text-[10px]">new gene</span>
                            </div>
                          ))}
                        </>
                      )}
                    </div>
                  </div>
                );
              })()}

              {/* ── Gene detail panel ───────────────────────────── */}
              <div className="flex-1 overflow-y-auto">
                {selected ? (
                  <div className="max-w-[880px] mx-auto px-5 py-4 space-y-3.5 pb-10">

                    {/* Header card */}
                    <div className="bg-[#0f0f1e] border border-white/7 rounded-[14px] p-5">
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0 flex-1">

                          {/* Name row */}
                          <div className="flex items-center gap-2 flex-wrap mb-1.5">
                            <h2 className="text-xl font-bold text-white font-mono">{selected.name}</h2>

                            <button
                              onClick={() => {
                                if (!job) return;
                                const next = toggleBookmark({
                                  geneId: selected.id,
                                  geneName: selected.name,
                                  locus: selected.locus,
                                  function: selected.function,
                                  confidence: selected.confidence,
                                  score: selected.score,
                                  is_dark: selected.is_dark,
                                  jobId: id,
                                  jobFilename: job.filename,
                                });
                                setBookmarked(next);
                                toast.success(next ? "Bookmarked" : "Bookmark removed");
                              }}
                              title={bookmarked ? "Remove bookmark" : "Bookmark gene"}
                              className={cn(
                                "p-1 rounded transition-colors",
                                bookmarked ? "text-amber-400 hover:text-amber-300" : "text-gray-600 hover:text-amber-400"
                              )}
                            >
                              <Bookmark size={14} fill={bookmarked ? "currentColor" : "none"} />
                            </button>

                            {/* Confidence badge */}
                            {selected.is_dark ? (
                              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full border tracking-wider"
                                style={{ background: "rgba(245,158,11,0.1)", color: "#f59e0b", borderColor: "rgba(245,158,11,0.25)" }}>
                                DARK MATTER
                              </span>
                            ) : selected.confidence && (
                              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full border tracking-wider"
                                style={{
                                  background: ha(confColor(selected.confidence), 0.1),
                                  color: confColor(selected.confidence),
                                  borderColor: ha(confColor(selected.confidence), 0.25),
                                }}>
                                {selected.confidence}
                              </span>
                            )}

                            {/* COG chip */}
                            <CogChip letter={selected.cog_category} size="lg" />

                            {/* Pfam badge */}
                            {selected.pfam_id && (
                              <span className="text-[11px] font-mono px-2 py-0.5 rounded-full border" style={{ background: "rgba(167,139,250,0.1)", color: "#c4b5fd", borderColor: "rgba(167,139,250,0.22)" }}>
                                {selected.pfam_id}
                              </span>
                            )}
                            {/* EC number — links to the ExPASy enzyme entry */}
                            {selected.ec_number && (
                              <a
                                href={`https://enzyme.expasy.org/EC/${selected.ec_number}`}
                                target="_blank" rel="noopener noreferrer"
                                title="Enzyme Commission number — view on ExPASy"
                                className="text-[11px] font-mono px-2 py-0.5 rounded-full border transition-colors hover:brightness-125"
                                style={{ background: "rgba(34,211,238,0.1)", color: "#67e8f9", borderColor: "rgba(34,211,238,0.25)" }}
                              >
                                EC {selected.ec_number}
                              </a>
                            )}
                          </div>

                          {/* Locus + coords + operon chip */}
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs text-gray-500 font-mono">{selected.locus}</span>
                            {selected.start != null && selected.end != null && (
                              <span className="text-xs text-gray-600 font-mono">
                                {selected.start.toLocaleString()}–{selected.end.toLocaleString()} · {selected.strand === -1 ? "−" : "+"}
                              </span>
                            )}
                            {selectedOperon && (
                              <span
                                className="inline-flex items-center gap-1.5 text-[10px] px-2 py-0.5 rounded-full border font-semibold"
                                style={{
                                  color: selectedOperon.color,
                                  borderColor: ha(selectedOperon.color, 0.4),
                                  background: ha(selectedOperon.color, 0.12),
                                }}
                              >
                                <span className="w-1.5 h-1.5 rounded-full" style={{ background: selectedOperon.color }} />
                                {selectedOperon.label} · {selectedOperon.genes.length} genes
                              </span>
                            )}
                          </div>

                          {/* Product */}
                          {(selected.normalized_product || selected.function) && (
                            <p className="text-sm text-gray-300 leading-relaxed mt-3 max-w-[560px]">
                              {selected.normalized_product || selected.function}
                            </p>
                          )}

                          {/* GO terms — clickable, resolve on QuickGO */}
                          {selected.go_terms && selected.go_terms.length > 0 && (
                            <div className="flex flex-wrap items-center gap-1.5 mt-3">
                              <span className="text-[9px] uppercase tracking-wider text-gray-600 mr-0.5">GO</span>
                              {selected.go_terms.map((go) => (
                                <a
                                  key={go}
                                  href={`https://www.ebi.ac.uk/QuickGO/term/${go}`}
                                  target="_blank" rel="noopener noreferrer"
                                  title="View this GO term on QuickGO"
                                  className="text-[10px] font-mono bg-white/4 border border-white/6 text-gray-400 px-2 py-0.5 rounded transition-colors hover:text-gray-200 hover:border-white/20"
                                >
                                  {go}
                                </a>
                              ))}
                            </div>
                          )}

                          {/* Annotation note */}
                          <div className="mt-4 pt-4 border-t border-white/5">
                            <div className="flex items-center gap-1.5 mb-2">
                              <StickyNote size={11} className="text-gray-600" />
                              <p className="text-[10px] text-gray-600 uppercase tracking-wider">Note</p>
                            </div>
                            <textarea
                              value={note}
                              onChange={(e) => {
                                setNoteState(e.target.value);
                                setNote(id, selected.id, e.target.value);
                              }}
                              placeholder="Add a private annotation note…"
                              rows={2}
                              className="w-full text-xs bg-white/[0.03] border border-white/6 rounded-lg px-3 py-2 text-gray-300 placeholder-gray-700 outline-none focus:border-indigo-500/40 resize-none transition-colors"
                            />
                          </div>
                        </div>

                        {/* Score */}
                        {selected.score != null && !selected.is_dark && (
                          <div className="text-right shrink-0">
                            <p className="text-[11px] text-gray-600 mb-0.5">Score</p>
                            <p className="text-4xl font-bold font-mono leading-none" style={{ color: confColor(selected.confidence) }}>
                              {selected.score.toFixed(2)}
                            </p>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* AMR / Virulence flags */}
                    {selectedFlags.length > 0 && (
                      <div className="bg-[#0f0f1e] border border-white/7 rounded-[14px] p-5">
                        <div className="flex items-center gap-2 mb-3">
                          <span className="text-xs font-semibold uppercase tracking-wider text-red-400">⚠ Resistance / Virulence Flags</span>
                          <span className="text-[10px] text-gray-600 ml-auto">heuristic match · overrides confidence color</span>
                        </div>
                        <div className="space-y-3">
                          {selectedFlags.map((hit, i) => {
                            const isAmr = hit.type === "amr";
                            return (
                              <div key={i} className="rounded-xl border px-3.5 py-3"
                                style={{
                                  background: isAmr ? "rgba(239,68,68,0.05)" : "rgba(249,115,22,0.05)",
                                  borderColor: isAmr ? "rgba(239,68,68,0.15)" : "rgba(249,115,22,0.15)",
                                }}>
                                <div className="flex items-center gap-2 mb-1">
                                  <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border"
                                    style={{
                                      color: isAmr ? "#f87171" : "#fb923c",
                                      background: isAmr ? "rgba(239,68,68,0.1)" : "rgba(249,115,22,0.1)",
                                      borderColor: isAmr ? "rgba(239,68,68,0.2)" : "rgba(249,115,22,0.2)",
                                    }}>
                                    {isAmr ? "AMR" : "VIR"}
                                  </span>
                                  <span className="text-xs font-medium" style={{ color: isAmr ? "#fca5a5" : "#fdba74" }}>{hit.label}</span>
                                  <span className="ml-auto text-[10px] text-gray-600 capitalize">{hit.category?.replace(/-/g, " ")}</span>
                                </div>
                                <p className="text-[11px] text-gray-400 leading-relaxed">{hit.description}</p>
                                <p className="text-[10px] mt-1.5" style={{ color: hit.confidence === "high" ? "#dc2626" : hit.confidence === "moderate" ? "#d97706" : "#6b7280" }}>
                                  Match confidence: {hit.confidence}
                                </p>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Dark matter card */}
                    {selected.is_dark && (
                      <>
                        <div className="border border-dashed rounded-[14px] p-4"
                          style={{ background: "rgba(245,158,11,0.03)", borderColor: "rgba(245,158,11,0.18)" }}>
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <div className="flex items-center gap-2 mb-1">
                                <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                                <span className="text-[11px] font-bold uppercase tracking-wider text-amber-300">Dark matter · discovery opportunity</span>
                              </div>
                              <p className="text-xs text-gray-400 leading-relaxed max-w-md">
                                No motif, domain, homology, or curated evidence. Added to the global dark-matter index as a high-priority research target.
                              </p>
                            </div>
                            <button
                              onClick={async () => {
                                try {
                                  if (watched) {
                                    await api.removeFromWatchlist(selected.locus);
                                    setWatched(false);
                                    toast.success("Removed from watchlist.");
                                  } else {
                                    await api.addToWatchlist(selected.locus, selected.name);
                                    setWatched(true);
                                    toast.success("Added to watchlist — you'll be notified if it gets annotated.");
                                  }
                                } catch {
                                  toast.error("Failed to update watchlist.");
                                }
                              }}
                              className={cn(
                                "shrink-0 text-xs px-3 py-1.5 rounded-lg border transition-colors",
                                watched
                                  ? "bg-indigo-600/15 border-indigo-500/30 text-indigo-300"
                                  : "bg-white/5 border-white/10 text-gray-400 hover:text-white"
                              )}
                            >
                              {watched ? "Watching ✓" : "Watch"}
                            </button>
                          </div>
                        </div>
                        <DarkMatterResearchCard gene={selected} />
                      </>
                    )}

                    {/* Evidence ladder */}
                    <EvidenceLadder gene={selected} />

                    {/* Confidence donut + competing hypotheses */}
                    {!selected.is_dark && selected.score != null && (
                      <div className="grid lg:grid-cols-2 gap-3.5">
                        <ConfidenceDonut gene={selected} operon={selectedOperon} />

                        {selected.competing_hypotheses && selected.competing_hypotheses.length > 0 && selected.function && (
                          <div className="bg-[#0f0f1e] border border-white/7 rounded-[14px] p-[18px]">
                            <div className="text-[11px] text-gray-400 font-semibold uppercase tracking-wider mb-1">Hypotheses considered</div>
                            <div className="text-[11px] text-gray-600 mb-3.5">
                              The engine ranked {1 + selected.competing_hypotheses.length} candidates before settling on the accepted one.
                            </div>
                            <div className="flex flex-col gap-3">
                              {(() => {
                                const items = [
                                  { hypothesis: selected.function!, confidence: selected.score!, accepted: true, reason: null },
                                  ...selected.competing_hypotheses.map((c) => ({ hypothesis: c.hypothesis, confidence: c.confidence, accepted: false, reason: c.reason_not_preferred })),
                                ].sort((a, b) => b.confidence - a.confidence);
                                const mx = Math.max(...items.map((i) => i.confidence), 1);
                                return items.map((item, idx) => (
                                  <div key={idx}>
                                    <div className="flex items-center justify-between gap-2 mb-1">
                                      <span className="text-xs font-medium truncate" style={{ color: item.accepted ? "#fff" : "#6b7280" }}>
                                        {item.accepted ? "✓" : "✕"} {item.hypothesis}
                                      </span>
                                      <span className="text-[11px] font-mono shrink-0" style={{ color: item.accepted ? "#34d399" : "#6b7280" }}>
                                        {(item.confidence * 100).toFixed(0)}%
                                      </span>
                                    </div>
                                    <div className="h-1.5 rounded-full overflow-hidden bg-white/5">
                                      <div className="h-full rounded-full" style={{
                                        width: `${Math.round(item.confidence / mx * 100)}%`,
                                        background: item.accepted ? "#34d399" : "#374151",
                                      }} />
                                    </div>
                                    {!item.accepted && item.reason && (
                                      <div className="text-[10px] text-gray-600 italic mt-1">Rejected: {item.reason}</div>
                                    )}
                                  </div>
                                ));
                              })()}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Domain architecture + amino-acid sequence */}
                    {selected.aa_sequence && <DomainSequenceCard gene={selected} />}

                    {/* Reasoning chain */}
                    {selected.reasoning_steps && selected.reasoning_steps.length > 0 && (
                      <ReasoningChain steps={selected.reasoning_steps} />
                    )}
                    {(!selected.reasoning_steps || selected.reasoning_steps.length === 0) && selected.reasoning && (
                      <div className="bg-[#0f0f1e] border border-white/7 rounded-[14px] p-5">
                        <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Reasoning</p>
                        <p className="text-xs text-gray-400 leading-relaxed italic">"{selected.reasoning}"</p>
                      </div>
                    )}

                    {/* Uncertainty notes */}
                    {selected.uncertainty_sources && selected.uncertainty_sources.length > 0 && (
                      <UncertaintyNotes sources={selected.uncertainty_sources} />
                    )}

                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-full text-center py-20">
                    <p className="text-gray-500 text-sm">Select a gene from the list to inspect it</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
