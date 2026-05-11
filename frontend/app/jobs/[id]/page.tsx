"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ChevronLeft, Download, Share2, CheckCircle2, Clock, AlertCircle, RefreshCw, XCircle, WifiOff } from "lucide-react";
import { api } from "@/lib/api";
import type { Job, GeneRow } from "@/lib/types";
import { AppNav } from "@/components/nav";
import { cn } from "@/lib/utils";

type GeneFilter = "all" | "high" | "moderate" | "low" | "dark";

function confidenceDot(c: string | null) {
  if (c === "HIGH") return "bg-emerald-400";
  if (c === "MODERATE") return "bg-amber-400";
  if (c === "LOW") return "bg-indigo-400";
  return "bg-gray-600";
}

export default function JobPage() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [selected, setSelected] = useState<GeneRow | null>(null);
  const [filter, setFilter] = useState<GeneFilter>("all");
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
    if (filter === "high") return g.confidence === "HIGH";
    if (filter === "moderate") return g.confidence === "MODERATE";
    if (filter === "low") return g.confidence === "LOW";
    if (filter === "dark") return g.is_dark;
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
            <div className="w-60 border-r border-white/5 flex flex-col overflow-hidden shrink-0">
              <div className="p-3 border-b border-white/5">
                <p className="text-xs text-gray-500 uppercase tracking-wider px-1 mb-2">Genes</p>
                <div className="flex gap-1 flex-wrap">
                  {(["all", "high", "moderate", "low", "dark"] as GeneFilter[]).map((f) => (
                    <button
                      key={f}
                      onClick={() => setFilter(f)}
                      className={cn(
                        "flex-1 text-xs py-1 rounded-md transition-colors capitalize",
                        filter === f
                          ? "bg-indigo-600/20 text-indigo-400 border border-indigo-500/30"
                          : "text-gray-500 hover:text-gray-300 hover:bg-white/5"
                      )}
                    >
                      {f}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
                {genes.length === 0 ? (
                  <p className="text-xs text-gray-600 px-2 py-4 text-center">No genes match this filter</p>
                ) : (
                  genes.map((g) => (
                    <button
                      key={g.id}
                      onClick={() => setSelected(g)}
                      className={cn(
                        "w-full text-left px-2.5 py-2 rounded-lg transition-colors",
                        selected?.id === g.id
                          ? "bg-indigo-600/15 border border-indigo-500/20"
                          : "hover:bg-white/5"
                      )}
                    >
                      <div className="flex items-center justify-between mb-0.5">
                        <span className={cn("text-xs font-medium", selected?.id === g.id ? "text-white" : "text-gray-300")}>
                          {g.name}
                        </span>
                        <span className={cn("w-1.5 h-1.5 rounded-full", g.is_dark ? "bg-amber-400" : confidenceDot(g.confidence))} />
                      </div>
                      <p className="text-xs text-gray-600 mono">{g.locus}</p>
                    </button>
                  ))
                )}
              </div>
            </div>

            {/* Gene detail panel */}
            <div className="flex-1 overflow-y-auto p-6">
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

              {/* Confidence bar */}
              {job.total_genes && job.total_genes > 0 && (
                <div className="bg-[#0f0f1e] border border-white/6 rounded-xl p-4 mb-6">
                  <p className="text-xs text-gray-400 font-medium mb-3">Confidence distribution</p>
                  <div className="flex rounded-full overflow-hidden h-2.5 mb-3">
                    <div className="bg-emerald-500" style={{ width: `${((job.high_confidence_count ?? 0) / job.total_genes) * 100}%` }} />
                    <div className="bg-amber-500" style={{ width: `${(((job.interpreted_genes ?? 0) - (job.high_confidence_count ?? 0)) / job.total_genes) * 100}%` }} />
                    <div className="bg-white/5 flex-1" />
                  </div>
                  <div className="flex gap-5 text-xs text-gray-500">
                    <span><span className="text-emerald-400">●</span> High {job.high_confidence_count ?? 0}</span>
                    <span><span className="text-amber-400">●</span> Other {(job.interpreted_genes ?? 0) - (job.high_confidence_count ?? 0)}</span>
                    <span><span className="text-gray-600">●</span> Dark {job.dark_count ?? 0}</span>
                  </div>
                </div>
              )}

              {/* Selected gene detail */}
              {selected ? (
                <div className="bg-[#0f0f1e] border border-white/6 rounded-xl p-5">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
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
                      </div>
                      <p className="text-xs text-gray-500 mono">{selected.locus}</p>
                    </div>
                    {selected.score != null && (
                      <div className="text-right">
                        <p className="text-xs text-gray-500">Confidence score</p>
                        <p className="text-2xl font-bold text-emerald-400 mono">{selected.score.toFixed(2)}</p>
                      </div>
                    )}
                  </div>

                  {selected.function && (
                    <p className="text-sm text-gray-300 leading-relaxed mb-5">{selected.function}</p>
                  )}

                  {selected.is_dark && (
                    <div className="bg-amber-500/5 border border-amber-500/15 rounded-xl p-4 mb-4">
                      <p className="text-sm text-amber-300 font-medium mb-1">Dark matter gene</p>
                      <p className="text-xs text-gray-400 leading-relaxed">
                        No motif hits, no domain evidence. This gene has zero functional annotation
                        across all databases. Added to the global dark matter index as a high-priority research target.
                      </p>
                    </div>
                  )}

                  {selected.evidence.length > 0 && (
                    <div className="mb-5">
                      <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Evidence chain</p>
                      <div className="space-y-2">
                        {selected.evidence.map((ev, i) => (
                          <div key={i} className="flex items-start gap-3 bg-white/2 border border-white/4 rounded-lg p-2.5">
                            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-1.5 shrink-0" />
                            <div>
                              <p className="text-xs font-medium text-gray-200">{ev.label}</p>
                              <p className="text-xs text-gray-600 mono">{ev.source} · confidence {ev.conf}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {selected.reasoning && (
                    <div className="pt-4 border-t border-white/5">
                      <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Reasoning</p>
                      <p className="text-xs text-gray-400 leading-relaxed italic">"{selected.reasoning}"</p>
                    </div>
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
