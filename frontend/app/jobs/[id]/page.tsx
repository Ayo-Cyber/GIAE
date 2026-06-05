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
import { toGff3, toTsv, toJson, toGenbank, downloadBlob } from "@/lib/export";
import { isBookmarked, toggleBookmark } from "@/lib/bookmarks";
import { getNote, setNote } from "@/lib/notes";
import { cn } from "@/lib/utils";
import {
  ConfidenceComposition,
  EvidenceLadder,
  ReasoningChain,
  CompetingHypothesesChart,
  UncertaintyNotes,
  DarkMatterResearchCard,
} from "@/components/explainability-panel";
import { GenomeTrack } from "@/components/genome-track";
import { DEMO_JOB_ID, demoJob } from "@/data/demo-data";
import { clusterOperons } from "@/lib/operons";
import type { Operon } from "@/lib/operons";
import { flagGenes } from "@/lib/amr";
import type { BioHit } from "@/lib/amr";

type GeneFilter = "all" | "high" | "moderate" | "low" | "dark" | "amr" | "virulence";

const FILTER_TABS: { key: GeneFilter; label: string; color?: string }[] = [
  { key: "all",       label: "All"    },
  { key: "high",      label: "High"   },
  { key: "moderate",  label: "Mod"    },
  { key: "low",       label: "Low"    },
  { key: "dark",      label: "Dark"   },
  { key: "amr",       label: "AMR",       color: "#f87171" },
  { key: "virulence", label: "Virulence",  color: "#fb923c" },
];

export default function JobPage() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob]           = useState<Job | null>(null);
  const [selected, setSelected] = useState<GeneRow | null>(null);
  const [filter, setFilter]     = useState<GeneFilter>("all");
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

  // Sync bookmark + note + watch state when selected gene changes
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

  // Load annotation history when job completes (if a previous run exists)
  useEffect(() => {
    if (job?.status !== "COMPLETED") return;
    api.getJobHistory(id)
      .then((h) => setHistoryDiff({ previous: h.previous_genes, current: h.current_genes }))
      .catch(() => {}); // 404 just means no previous run — silent
  }, [job?.status, id]);

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

  const genes = (job?.genes ?? []).filter((g) => {
    if (filter === "high"     && !(g.confidence === "HIGH" && !g.is_dark)) return false;
    if (filter === "moderate" && !(g.confidence === "MODERATE" && !g.is_dark)) return false;
    if (filter === "low"      && !((g.confidence === "LOW" || g.confidence === "SPECULATIVE") && !g.is_dark)) return false;
    if (filter === "dark"      && !g.is_dark) return false;
    if (filter === "amr"       && !amrFlags.has(g.id)) return false;
    if (filter === "virulence" && !(amrFlags.get(g.id) ?? []).some((h) => h.type === "virulence")) return false;
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
    /* Full viewport — sidebar nav on left, content to the right */
    <div className="h-screen overflow-hidden bg-[#0a0a14] flex">
      <AppNav />

      {/* Content column — fills space right of sidebar */}
      <div className="app-shell flex flex-col flex-1 min-w-0 h-screen overflow-hidden">

        {/* ── Top toolbar ─────────────────────────────────────────── */}
        <div className="shrink-0 h-12 border-b border-white/5 flex items-center gap-3 px-4 bg-[#0a0a14]">
          <Link href="/dashboard" className="text-gray-500 hover:text-gray-300 transition-colors">
            <ChevronLeft size={15} />
          </Link>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <p className="text-sm font-medium text-white truncate">{job?.filename ?? id}</p>
              {isDemo && (
                <span className="inline-flex items-center gap-1 text-[10px] text-cyan-200 bg-cyan-400/10 border border-cyan-400/20 px-1.5 py-0.5 rounded-full shrink-0">
                  <FlaskConical size={9} /> sample
                </span>
              )}
            </div>
            <p className="text-[11px] text-gray-500 mono">
              {job?.total_genes != null ? `${job.total_genes} genes · ${job.processing_time_seconds ?? "—"}s` : "Loading…"}
            </p>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-1.5 shrink-0">
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
                className="flex items-center gap-1.5 text-xs bg-white/5 hover:bg-white/8 border border-white/10 px-2.5 py-1.5 rounded-lg text-gray-400 transition-colors"
              >
                <Share2 size={11} /> {copied ? "Copied!" : "Share"}
              </button>
            )}

            {/* Export dropdown */}
            {job?.status === "COMPLETED" && (
              <div className="relative">
                <button
                  onClick={() => setExportOpen((v) => !v)}
                  className="flex items-center gap-1.5 text-xs bg-white/5 hover:bg-white/8 border border-white/10 px-2.5 py-1.5 rounded-lg text-gray-400 transition-colors"
                >
                  <Download size={11} /> Export
                </button>
                {exportOpen && (
                  <>
                    <div className="fixed inset-0 z-30" onClick={() => setExportOpen(false)} />
                    <div className="absolute right-0 top-8 z-40 bg-[#0f0f1e] border border-white/10 rounded-xl shadow-xl p-1.5 w-44">
                      {[
                        { label: "GFF3", ext: "gff3", mime: "text/plain",       fn: () => toGff3(job)    },
                        { label: "TSV",  ext: "tsv",  mime: "text/tab-separated-values", fn: () => toTsv(job) },
                        { label: "JSON", ext: "json", mime: "application/json", fn: () => toJson(job)    },
                        { label: "GenBank (simplified)", ext: "gbk", mime: "text/plain", fn: () => toGenbank(job) },
                      ].map(({ label, ext, mime, fn }) => (
                        <button
                          key={ext}
                          onClick={() => {
                            const base = job.filename.replace(/\.[^.]+$/, "");
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
                className="flex items-center gap-1.5 text-xs bg-white/5 hover:bg-white/8 border border-white/10 px-2.5 py-1.5 rounded-lg text-gray-400 transition-colors disabled:opacity-50"
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

        {/* ── Worker offline banner ───────────────────────────────── */}
        {isRunning && workerOnline === false && (
          <div className="shrink-0 mx-4 mt-3 flex items-center gap-3 bg-amber-500/10 border border-amber-500/20 rounded-xl px-4 py-2.5">
            <WifiOff size={14} className="text-amber-400 shrink-0" />
            <p className="text-xs text-amber-300">
              Worker not running — start it with{" "}
              <span className="mono bg-amber-500/10 px-1 rounded">make worker</span>
            </p>
          </div>
        )}

        {/* ── Initial loading skeleton ─────────────────────────────── */}
        {!job && !isDemo && (
          <div className="flex flex-1 overflow-hidden">
            <div className="w-64 border-r border-white/5 p-3 space-y-2">
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

        {/* ── Running state ─────────────────────────────────────────── */}
        {isRunning && (
          <div className="flex flex-col items-center justify-center flex-1 px-6 py-20 text-center">
            <div className="w-16 h-16 rounded-2xl bg-indigo-600/15 border border-indigo-500/25 flex items-center justify-center mb-6 relative">
              <Clock size={26} className="text-indigo-400 animate-spin" />
              <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-emerald-400 animate-pulse" />
            </div>
            <h2 className="text-lg font-semibold text-white mb-2">Interpreting genome…</h2>
            <p className="text-gray-400 text-sm mb-6">{job?.filename}</p>
            <p className="text-xs text-gray-500 mono">
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

        {/* ── Completed — three-pane workstation ────────────────────── */}
        {job?.status === "COMPLETED" && (
          <div className="flex flex-1 overflow-hidden">

            {/* Pane 1 — Gene list */}
            <div className="w-64 shrink-0 border-r border-white/5 flex flex-col overflow-hidden bg-[#0c0c18]">
              {/* Search + filters */}
              <div className="p-2.5 border-b border-white/5 space-y-2">
                <div className="relative">
                  <Search size={11} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-600 pointer-events-none" />
                  <input
                    type="text" value={query} onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search genes…"
                    className="w-full text-xs bg-white/4 border border-white/8 rounded-md pl-7 pr-2 py-1.5 text-gray-200 placeholder-gray-600 outline-none focus:border-indigo-500/40 transition-colors"
                  />
                </div>
                <div className="flex gap-1 flex-wrap">
                  {FILTER_TABS.map(({ key, label, color }) => {
                    const count = key === "amr" ? amrCount : key === "virulence" ? virulenceCount : null;
                    const active = filter === key;
                    return (
                      <button key={key} onClick={() => setFilter(key)}
                        className={cn(
                          "flex-1 text-[10px] py-1 rounded transition-colors flex items-center justify-center gap-0.5",
                          active
                            ? color
                              ? "border font-semibold"
                              : "bg-indigo-600/20 text-indigo-400 border border-indigo-500/30"
                            : "text-gray-600 hover:text-gray-400 border border-transparent"
                        )}
                        style={active && color ? { color, borderColor: color + "50", backgroundColor: color + "18" } : {}}
                      >
                        {label}
                        {count !== null && count > 0 && (
                          <span className="ml-0.5 text-[9px]">({count})</span>
                        )}
                      </button>
                    );
                  })}
                </div>
                <p className="text-[10px] text-gray-600 mono px-0.5">
                  {genes.length} / {job.total_genes ?? 0} genes
                </p>
              </div>

              {/* Gene rows */}
              <div className="flex-1 overflow-y-auto p-1.5 space-y-px">
                {genes.length === 0 ? (
                  <div className="px-2 py-8 text-center">
                    <p className="text-xs text-gray-600">No matches</p>
                    {(filter !== "all" || query) && (
                      <button onClick={() => { setFilter("all"); setQuery(""); }}
                        className="text-[11px] text-indigo-400 hover:text-indigo-300 mt-1.5">
                        Clear filters
                      </button>
                    )}
                  </div>
                ) : genes.map((g) => {
                  const isSel    = selected?.id === g.id;
                  const operon   = geneToOperon.get(g.id);
                  const gFlags   = amrFlags.get(g.id) ?? [];
                  const hasAmr   = gFlags.some((h: BioHit) => h.type === "amr");
                  const hasVir   = gFlags.some((h: BioHit) => h.type === "virulence");
                  const stripCol = g.is_dark ? "bg-amber-600"
                    : g.confidence === "HIGH"     ? "bg-emerald-400"
                    : g.confidence === "MODERATE" ? "bg-amber-500"
                    : "bg-indigo-400";
                  return (
                    <button key={g.id} onClick={() => setSelected(g)}
                      className={cn(
                        "group w-full text-left pl-2 pr-2.5 py-2 rounded-lg transition-all relative overflow-hidden",
                        isSel ? "bg-indigo-600/15 ring-1 ring-indigo-500/30" : "hover:bg-white/5"
                      )}
                    >
                      <span className={cn("absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r", stripCol)} />
                      <div className="pl-2">
                        <div className="flex items-center justify-between gap-2 mb-0.5">
                          <span className={cn("text-xs font-medium truncate", isSel ? "text-white" : "text-gray-200")}>
                            {g.name}
                          </span>
                          <div className="flex items-center gap-1 shrink-0">
                            {hasAmr && (
                              <span className="text-[9px] px-1 py-0.5 rounded bg-red-500/15 text-red-400 border border-red-500/25 font-semibold leading-none">AMR</span>
                            )}
                            {hasVir && (
                              <span className="text-[9px] px-1 py-0.5 rounded bg-orange-500/15 text-orange-400 border border-orange-500/25 font-semibold leading-none">VIR</span>
                            )}
                            {operon && (
                              <span
                                className="w-2 h-2 rounded-full"
                                style={{ backgroundColor: operon.color }}
                                title={operon.label}
                              />
                            )}
                            {g.length != null && (
                              <span className="text-[10px] mono text-gray-600">
                                {g.length < 1000 ? `${g.length}b` : `${(g.length / 1000).toFixed(1)}k`}
                              </span>
                            )}
                          </div>
                        </div>
                        <p className="text-[11px] text-gray-500 truncate leading-tight">
                          {g.normalized_product ?? g.function ?? (g.is_dark ? "Dark matter" : "Unannotated")}
                        </p>
                        <p className="text-[10px] text-gray-700 mono mt-0.5 truncate">{g.locus}</p>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Pane 2 — Detail panel */}
            <div className="flex-1 overflow-y-auto flex flex-col min-w-0">
              {/* Genome track — pinned at top of detail area */}
              <div className="shrink-0 border-b border-white/5 px-4 py-3 bg-[#0a0a14]">
                <GenomeTrack
                  genes={job.genes ?? []}
                  selectedId={selected?.id ?? null}
                  onSelect={setSelected}
                  operons={operons}
                  geneToOperon={geneToOperon}
                />
              </div>

              {/* Stats bar */}
              <div className="shrink-0 flex items-center gap-6 px-5 py-3 border-b border-white/5 bg-[#0a0a14]">
                {[
                  { v: String(job.total_genes ?? 0),        label: "Genes",       c: "text-white"       },
                  { v: String(job.high_confidence_count ?? 0), label: "High conf", c: "text-emerald-400" },
                  { v: String(job.dark_count ?? 0),          label: "Dark matter", c: "text-amber-400"   },
                  { v: `${successRate}%`,                    label: "Success",     c: "text-indigo-400"  },
                ].map((s) => (
                  <div key={s.label} className="flex items-baseline gap-2">
                    <span className={cn("text-lg font-bold mono", s.c)}>{s.v}</span>
                    <span className="text-xs text-gray-500">{s.label}</span>
                  </div>
                ))}

                {/* Confidence bar */}
                {job.total_genes && job.total_genes > 0 && (() => {
                  const all  = job.genes ?? [];
                  const high = all.filter((g) => g.confidence === "HIGH" && !g.is_dark).length;
                  const mod  = all.filter((g) => g.confidence === "MODERATE" && !g.is_dark).length;
                  const low  = all.filter((g) => (g.confidence === "LOW" || g.confidence === "SPECULATIVE") && !g.is_dark).length;
                  const dark = all.filter((g) => g.is_dark).length;
                  const t    = job.total_genes;
                  return (
                    <div className="flex-1 flex items-center gap-2 min-w-0 ml-2">
                      <div className="flex-1 flex rounded-full overflow-hidden h-1.5 bg-white/4">
                        {[
                          { n: high, c: "bg-emerald-500" }, { n: mod, c: "bg-amber-500" },
                          { n: low,  c: "bg-indigo-500"  }, { n: dark, c: "bg-amber-700" },
                        ].map((s, i) => s.n > 0 ? (
                          <div key={i} className={s.c} style={{ width: `${(s.n / t) * 100}%` }} />
                        ) : null)}
                      </div>
                    </div>
                  );
                })()}
              </div>

              {/* Annotation history diff banner */}
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
                                <span className="mono text-gray-600">{p?.is_dark ? "dark" : p?.confidence ?? "—"}</span>
                                <span className="text-gray-600">→</span>
                                <span className={cn("mono", g.is_dark ? "text-amber-400" : g.confidence === "HIGH" ? "text-emerald-400" : "text-indigo-400")}>
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

              {/* Selected gene detail */}
              <div className="flex-1 p-5 space-y-4 overflow-y-auto">
                {selected ? (
                  <>
                    {/* Gene header */}
                    <div className="bg-[#0f0f1e] border border-white/6 rounded-xl p-5">
                      <div className="flex items-start justify-between gap-4 mb-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap mb-1">
                            <h3 className="text-base font-semibold text-white">{selected.name}</h3>
                            {/* Bookmark toggle */}
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
                                bookmarked
                                  ? "text-amber-400 hover:text-amber-300"
                                  : "text-gray-600 hover:text-amber-400"
                              )}
                            >
                              <Bookmark size={14} fill={bookmarked ? "currentColor" : "none"} />
                            </button>
                            {selected.confidence && (
                              <span className={cn("text-xs px-2 py-0.5 rounded-full border",
                                selected.confidence === "HIGH"     ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                                : selected.confidence === "MODERATE" ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                                : "bg-indigo-500/10 text-indigo-400 border-indigo-500/20"
                              )}>{selected.confidence}</span>
                            )}
                            {selected.is_dark && (
                              <span className="text-xs px-2 py-0.5 rounded-full border bg-amber-500/10 text-amber-400 border-amber-500/20">
                                DARK MATTER
                              </span>
                            )}
                            {selected.pfam_id && (
                              <span className="text-xs px-2 py-0.5 rounded-full border bg-purple-500/10 text-purple-400 border-purple-500/20 mono">
                                {selected.pfam_id}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <p className="text-xs text-gray-500 mono">{selected.locus}</p>
                            {selectedOperon && (
                              <span
                                className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full border font-medium"
                                style={{
                                  color: selectedOperon.color,
                                  borderColor: selectedOperon.color + "40",
                                  backgroundColor: selectedOperon.color + "15",
                                }}
                              >
                                <span
                                  className="w-1.5 h-1.5 rounded-full"
                                  style={{ backgroundColor: selectedOperon.color }}
                                />
                                {selectedOperon.label} · {selectedOperon.genes.length} genes
                              </span>
                            )}
                          </div>
                        </div>
                        {selected.score != null && (
                          <div className="text-right shrink-0">
                            <p className="text-xs text-gray-500 mb-0.5">Score</p>
                            <p className={cn("text-3xl font-bold mono",
                              selected.confidence === "HIGH"     ? "text-emerald-400"
                              : selected.confidence === "MODERATE" ? "text-amber-400"
                              : selected.confidence === "LOW"      ? "text-indigo-400"
                              : "text-gray-500"
                            )}>{selected.score.toFixed(2)}</p>
                          </div>
                        )}
                      </div>
                      {(selected.normalized_product || selected.function) && (
                        <p className="text-sm text-gray-300 leading-relaxed">
                          {selected.normalized_product || selected.function}
                        </p>
                      )}
                      {selected.go_terms && selected.go_terms.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mt-3">
                          {selected.go_terms.map((go) => (
                            <span key={go} className="text-[10px] mono bg-white/4 border border-white/6 text-gray-400 px-2 py-0.5 rounded">{go}</span>
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

                    {/* AMR / Virulence flags */}
                    {selectedFlags.length > 0 && (
                      <div className="bg-[#0f0f1e] border border-white/6 rounded-xl p-5">
                        <div className="flex items-center gap-2 mb-3">
                          <span className="text-xs font-semibold uppercase tracking-wider text-red-400">
                            ⚠ Resistance / Virulence Flags
                          </span>
                          <span className="text-[10px] text-gray-600 ml-auto">heuristic match</span>
                        </div>
                        <div className="space-y-3">
                          {selectedFlags.map((hit, i) => {
                            const isAmr = hit.type === "amr";
                            return (
                              <div key={i} className={cn(
                                "rounded-lg border px-3.5 py-3",
                                isAmr
                                  ? "bg-red-500/5 border-red-500/15"
                                  : "bg-orange-500/5 border-orange-500/15"
                              )}>
                                <div className="flex items-center gap-2 mb-1">
                                  <span className={cn(
                                    "text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border",
                                    isAmr
                                      ? "text-red-400 bg-red-500/10 border-red-500/20"
                                      : "text-orange-400 bg-orange-500/10 border-orange-500/20"
                                  )}>
                                    {isAmr ? "AMR" : "VIR"}
                                  </span>
                                  <span className={cn(
                                    "text-xs font-medium",
                                    isAmr ? "text-red-300" : "text-orange-300"
                                  )}>{hit.label}</span>
                                  <span className="ml-auto text-[10px] text-gray-600 capitalize">{hit.category.replace(/-/g, " ")}</span>
                                </div>
                                <p className="text-[11px] text-gray-400 leading-relaxed">{hit.description}</p>
                                <p className={cn(
                                  "text-[10px] mt-1.5",
                                  hit.confidence === "high"     ? "text-red-500/60"    :
                                  hit.confidence === "moderate" ? "text-amber-500/60"  : "text-gray-600"
                                )}>
                                  Match confidence: {hit.confidence}
                                </p>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {selected.is_dark && (
                      <>
                        <div className="bg-amber-500/5 border border-amber-500/15 rounded-xl p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-sm text-amber-300 font-medium mb-1">Dark matter gene</p>
                              <p className="text-xs text-gray-400 leading-relaxed">
                                No motif hits, no domain evidence. Added to the global dark matter index as a high-priority research target.
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

                    <EvidenceLadder evidence={selected.evidence} isDark={selected.is_dark} />

                    {!selected.is_dark && selected.score != null && (
                      <div className="grid lg:grid-cols-2 gap-4">
                        <ConfidenceComposition evidence={selected.evidence} score={selected.score} level={selected.confidence} />
                        {selected.competing_hypotheses && selected.competing_hypotheses.length > 0 && selected.function && (
                          <CompetingHypothesesChart
                            primary={{ hypothesis: selected.function, confidence: selected.score }}
                            competing={selected.competing_hypotheses}
                          />
                        )}
                      </div>
                    )}

                    {selected.reasoning_steps && selected.reasoning_steps.length > 0 && (
                      <ReasoningChain steps={selected.reasoning_steps} />
                    )}
                    {(!selected.reasoning_steps || selected.reasoning_steps.length === 0) && selected.reasoning && (
                      <div className="bg-[#0f0f1e] border border-white/6 rounded-xl p-5">
                        <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Reasoning</p>
                        <p className="text-xs text-gray-400 leading-relaxed italic">"{selected.reasoning}"</p>
                      </div>
                    )}
                    {selected.uncertainty_sources && selected.uncertainty_sources.length > 0 && (
                      <UncertaintyNotes sources={selected.uncertainty_sources} />
                    )}
                  </>
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
