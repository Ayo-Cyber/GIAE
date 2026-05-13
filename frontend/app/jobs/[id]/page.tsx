"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ChevronLeft, Download, Share2, CheckCircle2, Clock, AlertCircle, RefreshCw, XCircle, WifiOff, Search } from "lucide-react";
import { api } from "@/lib/api";
import type { Job, GeneRow } from "@/lib/types";
import { AppNav } from "@/components/nav";
import { cn } from "@/lib/utils";
import {
  ConfidenceComposition,
  ReasoningChain,
  CompetingHypothesesChart,
  UncertaintyNotes,
} from "@/components/explainability-panel";
import { GenomeTrack } from "@/components/genome-track";

type GeneFilter = "all" | "high" | "moderate" | "low" | "dark";

export default function JobPage() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [selected, setSelected] = useState<GeneRow | null>(null);
  const [filter, setFilter] = useState<GeneFilter>("all");
  const [query, setQuery] = useState("");
  const [rerunning, setRerunning] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [copied, setCopied] = useState(false);
  const [workerOnline, setWorkerOnline] = useState<boolean | null>(null);

  useEffect(() => {
    // Initial fetch
    api.getJob(id).then((j) => {
      setJob(j);
      if (j.genes?.length > 0) setSelected(j.genes[0]);
    });

    // Poll until done
    const stop = api.pollJob(id, (j) => {
      setJob(j);
      if (j.genes?.length > 0 && !selected) setSelected(j.genes[0]);
    });
    return stop;
  }, [id]);

  useEffect(() => {
    if (job?.status !== "PENDING" && job?.status !== "RUNNING") return;
    api.workerStatus().then((s) => setWorkerOnline(s.online)).catch(() => setWorkerOnline(false));
  }, [job?.status]);

  const isRunning = job?.status === "RUNNING" || job?.status === "PENDING";
  const isCancellable = job?.status === "PENDING" || job?.status === "RUNNING";
  const genes = (job?.genes ?? []).filter((g) => {
    if (filter === "high" && !(g.confidence === "HIGH" && !g.is_dark)) return false;
    if (filter === "moderate" && !(g.confidence === "MODERATE" && !g.is_dark)) return false;
    if (filter === "low" && !((g.confidence === "LOW" || g.confidence === "SPECULATIVE") && !g.is_dark)) return false;
    if (filter === "dark" && !g.is_dark) return false;
    if (query.trim()) {
      const q = query.trim().toLowerCase();
      const hay = `${g.name} ${g.locus} ${g.function ?? ""} ${g.normalized_product ?? ""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  const successRate =
    job?.total_genes && job.total_genes > 0
      ? Math.round(((job.interpreted_genes ?? 0) / job.total_genes) * 100)
      : 0;

  return (
    <div className="min-h-screen bg-[#0a0a14] flex flex-col">
      <AppNav />
      <div className="pt-14 flex flex-col flex-1">
        {/* Sub-header */}
        <div className="border-b border-white/5 px-6 py-3 flex items-center gap-3">
          <Link href="/dashboard" className="text-gray-500 hover:text-white transition-colors">
            <ChevronLeft size={16} />
          </Link>
          <div className="flex-1">
            <p className="text-sm font-semibold text-white">{job?.filename ?? id}</p>
            <p className="text-xs text-gray-500 mono">
              {job?.total_genes != null ? `${job.total_genes} genes` : "Loading…"}
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => {
                navigator.clipboard.writeText(window.location.href);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              }}
              className="flex items-center gap-1.5 text-xs bg-white/5 hover:bg-white/8 border border-white/10 px-3 py-1.5 rounded-lg text-gray-300 transition-colors"
            >
              <Share2 size={12} /> {copied ? "Copied!" : "Share"}
            </button>
            {isCancellable && (
              <button
                onClick={async () => {
                  setCancelling(true);
                  try {
                    await api.cancelJob(id);
                    const j = await api.getJob(id);
                    setJob(j);
                  } finally {
                    setCancelling(false);
                  }
                }}
                disabled={cancelling}
                className="flex items-center gap-1.5 text-xs bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 px-3 py-1.5 rounded-lg text-red-400 transition-colors disabled:opacity-50"
              >
                <XCircle size={12} className={cancelling ? "animate-spin" : ""} />
                {cancelling ? "Cancelling…" : "Cancel"}
              </button>
            )}
            {(job?.status === "COMPLETED" || job?.status === "FAILED") && (
              <button
                onClick={async () => {
                  setRerunning(true);
                  await api.rerunJob(id);
                  const j = await api.getJob(id);
                  setJob(j);
                  setSelected(null);
                  setRerunning(false);
                }}
                disabled={rerunning}
                className="flex items-center gap-1.5 text-xs bg-white/5 hover:bg-white/8 border border-white/10 px-3 py-1.5 rounded-lg text-gray-300 transition-colors disabled:opacity-50"
              >
                <RefreshCw size={12} className={rerunning ? "animate-spin" : ""} /> Re-run
              </button>
            )}
            {job?.report_url && (
              <a
                href={job.report_url}
                target="_blank"
                className="flex items-center gap-1.5 text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1.5 rounded-lg font-medium transition-colors"
              >
                <Download size={12} /> Full report
              </a>
            )}
          </div>
        </div>

        {/* Worker offline warning */}
        {isRunning && workerOnline === false && (
          <div className="mx-6 mt-4 flex items-center gap-3 bg-amber-500/10 border border-amber-500/20 rounded-xl px-4 py-3">
            <WifiOff size={15} className="text-amber-400 shrink-0" />
            <div>
              <p className="text-sm text-amber-300 font-medium">Worker not running</p>
              <p className="text-xs text-amber-400/70">
                Run <span className="mono bg-amber-500/10 px-1 rounded">make worker</span> (or <span className="mono bg-amber-500/10 px-1 rounded">make dev</span>) in your terminal to start processing.
              </p>
            </div>
          </div>
        )}

        {/* Running state */}
        {isRunning && (
          <div className="flex flex-col items-center justify-center flex-1 px-6 py-20 text-center">
            <div className="w-16 h-16 rounded-2xl bg-indigo-600/15 border border-indigo-500/25 flex items-center justify-center mb-6 relative">
              <Clock size={26} className="text-indigo-400 animate-spin" />
              <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-emerald-400 animate-pulse" />
            </div>
            <h2 className="text-lg font-semibold text-white mb-2">Interpreting genome…</h2>
            <p className="text-gray-400 text-sm mb-6">{job?.filename}</p>
            <div className="w-full max-w-sm bg-[#0f0f1e] border border-white/6 rounded-xl p-5">
              <p className="text-xs text-gray-500 mono text-center">
                {job?.status === "PENDING" ? "Queued — waiting for worker" : "Running GIAE pipeline…"}
              </p>
            </div>
          </div>
        )}

        {/* Cancelled state */}
        {job?.status === "CANCELLED" && (
          <div className="flex flex-col items-center justify-center flex-1 px-6 py-20 text-center">
            <XCircle size={32} className="text-gray-500 mb-4" />
            <h2 className="text-lg font-semibold text-white mb-2">Job cancelled</h2>
            <p className="text-sm text-gray-400">This job was cancelled before it completed.</p>
          </div>
        )}

        {/* Failed state */}
        {job?.status === "FAILED" && (
          <div className="flex flex-col items-center justify-center flex-1 px-6 py-20 text-center">
            <AlertCircle size={32} className="text-red-400 mb-4" />
            <h2 className="text-lg font-semibold text-white mb-2">Job failed</h2>
            <p className="text-sm text-gray-400">{job.error_message ?? "Unknown error"}</p>
          </div>
        )}

        {/* Completed state */}
        {job?.status === "COMPLETED" && (
          <div className="flex flex-1 overflow-hidden" style={{ height: "calc(100vh - 112px)" }}>
            {/* Gene list sidebar */}
            <div className="w-72 border-r border-white/5 flex flex-col overflow-hidden shrink-0 bg-[#0c0c18]">
              <div className="p-3 border-b border-white/5 space-y-2.5">
                <div className="flex items-center justify-between">
                  <p className="text-xs text-gray-500 uppercase tracking-wider">Genes</p>
                  <p className="text-[10px] text-gray-600 mono">
                    {genes.length}/{job?.total_genes ?? 0}
                  </p>
                </div>
                {/* Search */}
                <div className="relative">
                  <Search size={11} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-600 pointer-events-none" />
                  <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search name, locus, function…"
                    className="w-full text-xs bg-white/4 border border-white/8 rounded-md pl-7 pr-2 py-1.5 text-gray-200 placeholder-gray-600 outline-none focus:border-indigo-500/40 focus:bg-white/6 transition-colors"
                  />
                </div>
                {/* Filter chips */}
                <div className="flex gap-1 flex-wrap">
                  {(["all", "high", "moderate", "low", "dark"] as GeneFilter[]).map((f) => (
                    <button
                      key={f}
                      onClick={() => setFilter(f)}
                      className={cn(
                        "flex-1 text-[11px] py-1 rounded-md transition-colors capitalize",
                        filter === f
                          ? "bg-indigo-600/20 text-indigo-400 border border-indigo-500/30"
                          : "text-gray-500 hover:text-gray-300 hover:bg-white/5 border border-transparent"
                      )}
                    >
                      {f}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-1.5 space-y-0.5">
                {genes.length === 0 ? (
                  <div className="px-2 py-8 text-center">
                    <p className="text-xs text-gray-600">No matches</p>
                    {(filter !== "all" || query) && (
                      <button
                        onClick={() => { setFilter("all"); setQuery(""); }}
                        className="text-[11px] text-indigo-400 hover:text-indigo-300 mt-1.5"
                      >
                        Clear filters
                      </button>
                    )}
                  </div>
                ) : (
                  genes.map((g) => {
                    const isSel = selected?.id === g.id;
                    const isDark = g.is_dark;
                    const stripColour = isDark
                      ? "bg-amber-700"
                      : g.confidence === "HIGH" ? "bg-emerald-400"
                      : g.confidence === "MODERATE" ? "bg-amber-500"
                      : g.confidence === "LOW" || g.confidence === "SPECULATIVE" ? "bg-indigo-400"
                      : "bg-gray-700";
                    const label = g.normalized_product ?? g.function ?? (isDark ? "Dark matter" : "Unannotated");
                    return (
                      <button
                        key={g.id}
                        onClick={() => setSelected(g)}
                        className={cn(
                          "group w-full text-left pl-2 pr-2.5 py-2 rounded-lg transition-all relative overflow-hidden",
                          isSel
                            ? "bg-indigo-600/15 ring-1 ring-indigo-500/30"
                            : "hover:bg-white/5"
                        )}
                      >
                        {/* Left confidence strip */}
                        <span className={cn("absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r", stripColour)} />
                        <div className="pl-2">
                          <div className="flex items-center justify-between mb-0.5 gap-2">
                            <span className={cn("text-xs font-medium truncate", isSel ? "text-white" : "text-gray-200")}>
                              {g.name}
                            </span>
                            <span className="flex items-center gap-1.5 shrink-0">
                              {g.strand === -1 && (
                                <span className="text-[9px] mono text-gray-600">−</span>
                              )}
                              {g.length != null && (
                                <span className="text-[10px] mono text-gray-600">
                                  {g.length < 1000 ? `${g.length}b` : `${(g.length / 1000).toFixed(1)}k`}
                                </span>
                              )}
                            </span>
                          </div>
                          <p className="text-[11px] text-gray-500 truncate leading-tight">
                            {label}
                          </p>
                          <p className="text-[10px] text-gray-700 mono mt-0.5 truncate">
                            {g.locus}
                          </p>
                        </div>
                      </button>
                    );
                  })
                )}
              </div>
            </div>

            {/* Gene detail panel */}
            <div className="flex-1 overflow-y-auto p-6">
              {/* Genome map */}
              <div className="mb-6">
                <GenomeTrack
                  genes={job.genes ?? []}
                  selectedId={selected?.id ?? null}
                  onSelect={setSelected}
                />
              </div>

              {/* Summary cards */}
              <div className="grid grid-cols-4 gap-3 mb-6">
                {[
                  { v: String(job.total_genes ?? 0), l: "Total Genes", c: "text-white" },
                  { v: String(job.high_confidence_count ?? 0), l: "High Confidence", c: "text-emerald-400" },
                  { v: String(job.dark_count ?? 0), l: "Dark Matter", c: "text-amber-400" },
                  { v: `${successRate}%`, l: "Success Rate", c: "text-indigo-400" },
                ].map((s) => (
                  <div key={s.l} className="bg-[#0f0f1e] border border-white/6 rounded-xl p-3 text-center">
                    <p className={`text-xl font-bold ${s.c}`}>{s.v}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{s.l}</p>
                  </div>
                ))}
              </div>

              {/* Confidence distribution */}
              {job.total_genes && job.total_genes > 0 && (() => {
                const total = job.total_genes;
                const allGenes = job.genes ?? [];
                const high = allGenes.filter((g) => g.confidence === "HIGH" && !g.is_dark).length;
                const moderate = allGenes.filter((g) => g.confidence === "MODERATE" && !g.is_dark).length;
                const low = allGenes.filter((g) => (g.confidence === "LOW" || g.confidence === "SPECULATIVE") && !g.is_dark).length;
                const dark = allGenes.filter((g) => g.is_dark).length;
                const unscored = Math.max(total - high - moderate - low - dark, 0);
                const segs: { count: number; color: string; label: string; dot: string }[] = [
                  { count: high, color: "bg-emerald-500", label: "High", dot: "bg-emerald-400" },
                  { count: moderate, color: "bg-amber-500", label: "Moderate", dot: "bg-amber-400" },
                  { count: low, color: "bg-indigo-500", label: "Low", dot: "bg-indigo-400" },
                  { count: dark, color: "bg-amber-700", label: "Dark", dot: "bg-amber-600" },
                  { count: unscored, color: "bg-white/8", label: "Unscored", dot: "bg-gray-600" },
                ];
                return (
                  <div className="bg-[#0f0f1e] border border-white/6 rounded-xl p-4 mb-6">
                    <p className="text-xs text-gray-400 font-medium mb-3">Confidence distribution</p>
                    <div className="flex rounded-full overflow-hidden h-2.5 mb-3 bg-white/4">
                      {segs.map((s) =>
                        s.count > 0 ? (
                          <div
                            key={s.label}
                            className={s.color}
                            style={{ width: `${(s.count / total) * 100}%` }}
                            title={`${s.label}: ${s.count} (${Math.round((s.count / total) * 100)}%)`}
                          />
                        ) : null
                      )}
                    </div>
                    <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-gray-500">
                      {segs.map((s) =>
                        s.count > 0 ? (
                          <span key={s.label} className="flex items-center gap-1.5">
                            <span className={cn("w-1.5 h-1.5 rounded-full", s.dot)} />
                            {s.label} <span className="text-gray-400 mono">{s.count}</span>
                          </span>
                        ) : null
                      )}
                    </div>
                  </div>
                );
              })()}

              {/* Selected gene detail */}
              {selected ? (
                <div className="space-y-4">
                  {/* Header card */}
                  <div className="bg-[#0f0f1e] border border-white/6 rounded-xl p-5">
                    <div className="flex items-start justify-between mb-4">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <h3 className="text-white font-semibold">{selected.name}</h3>
                          {selected.confidence && (
                            <span className={cn(
                              "text-xs px-2 py-0.5 rounded-full border",
                              selected.confidence === "HIGH"
                                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                                : selected.confidence === "MODERATE"
                                ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                                : "bg-indigo-500/10 text-indigo-400 border-indigo-500/20"
                            )}>
                              {selected.confidence}
                            </span>
                          )}
                          {selected.is_dark && (
                            <span className="text-xs px-2 py-0.5 rounded-full border bg-amber-500/10 text-amber-400 border-amber-500/20">
                              DARK MATTER
                            </span>
                          )}
                          {selected.cog_category && (
                            <span
                              className="text-xs px-2 py-0.5 rounded-full border bg-indigo-500/10 text-indigo-400 border-indigo-500/20"
                              title={selected.cog_name ?? undefined}
                            >
                              COG {selected.cog_category}
                            </span>
                          )}
                          {selected.pfam_id && (
                            <span className="text-xs px-2 py-0.5 rounded-full border bg-purple-500/10 text-purple-400 border-purple-500/20 mono">
                              {selected.pfam_id}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-gray-500 mono">{selected.locus}</p>
                      </div>
                      {selected.score != null && (
                        <div className="text-right shrink-0 ml-3">
                          <p className="text-xs text-gray-500">Score</p>
                          <p className={cn(
                            "text-2xl font-bold mono",
                            selected.confidence === "HIGH" ? "text-emerald-400"
                              : selected.confidence === "MODERATE" ? "text-amber-400"
                              : selected.confidence === "LOW" ? "text-indigo-400"
                              : "text-gray-500"
                          )}>
                            {selected.score.toFixed(2)}
                          </p>
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
                          <span
                            key={go}
                            className="text-[10px] mono bg-white/4 border border-white/6 text-gray-400 px-2 py-0.5 rounded"
                          >
                            {go}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Dark matter callout — full width */}
                  {selected.is_dark && (
                    <div className="bg-amber-500/5 border border-amber-500/15 rounded-xl p-4">
                      <p className="text-sm text-amber-300 font-medium mb-1">Dark matter gene</p>
                      <p className="text-xs text-gray-400 leading-relaxed">
                        No motif hits, no domain evidence. This gene has zero functional annotation
                        across all databases. Added to the global dark matter index as a
                        high-priority research target.
                      </p>
                    </div>
                  )}

                  {/* Explainability grid */}
                  {!selected.is_dark && selected.score != null && (
                    <div className="grid lg:grid-cols-2 gap-4">
                      <ConfidenceComposition
                        evidence={selected.evidence}
                        score={selected.score}
                        level={selected.confidence}
                      />
                      {selected.competing_hypotheses && selected.competing_hypotheses.length > 0 && selected.function && (
                        <CompetingHypothesesChart
                          primary={{ hypothesis: selected.function, confidence: selected.score }}
                          competing={selected.competing_hypotheses}
                        />
                      )}
                    </div>
                  )}

                  {/* Reasoning chain — full width */}
                  {selected.reasoning_steps && selected.reasoning_steps.length > 0 && (
                    <ReasoningChain steps={selected.reasoning_steps} />
                  )}

                  {/* Fallback: text reasoning if no steps array */}
                  {(!selected.reasoning_steps || selected.reasoning_steps.length === 0) && selected.reasoning && (
                    <div className="bg-[#0f0f1e] border border-white/6 rounded-xl p-5">
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
                <div className="bg-[#0f0f1e] border border-white/6 rounded-xl p-8 text-center">
                  <p className="text-gray-500 text-sm">Select a gene from the sidebar to see details</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
