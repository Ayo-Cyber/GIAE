"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Job, GeneRow } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Dna, AlertCircle, Search } from "lucide-react";
import {
  EvidenceLadder, ConfidenceComposition,
  ReasoningChain, CompetingHypothesesChart,
} from "@/components/explainability-panel";
import { GenomeTrack } from "@/components/genome-track";

export default function SharedReportPage() {
  const { token } = useParams<{ token: string }>();
  const [job, setJob]           = useState<Job | null>(null);
  const [selected, setSelected] = useState<GeneRow | null>(null);
  const [error, setError]       = useState(false);
  const [query, setQuery]       = useState("");

  useEffect(() => {
    api.getSharedJob(token)
      .then((j) => { setJob(j); setSelected(j.genes[0] ?? null); })
      .catch(() => setError(true));
  }, [token]);

  const genes = (job?.genes ?? []).filter((g) => {
    if (!query.trim()) return true;
    const q = query.toLowerCase();
    return `${g.name} ${g.locus} ${g.function ?? ""}`.toLowerCase().includes(q);
  });

  if (error) return (
    <div className="min-h-screen bg-[#0a0a14] flex flex-col items-center justify-center text-center px-6">
      <AlertCircle size={32} className="text-red-400 mb-4" />
      <h1 className="text-lg font-semibold text-white mb-2">Report not found</h1>
      <p className="text-sm text-gray-400 mb-6">This share link may have expired or been removed.</p>
      <Link href="/" className="text-sm text-indigo-400 hover:text-indigo-300 transition-colors">← Go to GIAE</Link>
    </div>
  );

  if (!job) return (
    <div className="min-h-screen bg-[#0a0a14] flex items-center justify-center">
      <div className="w-8 h-8 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
    </div>
  );

  const successRate = job.total_genes && job.total_genes > 0
    ? Math.round(((job.interpreted_genes ?? 0) / job.total_genes) * 100)
    : 0;

  return (
    <div className="h-screen overflow-hidden bg-[#0a0a14] flex flex-col">
      {/* Top bar */}
      <div className="shrink-0 h-12 border-b border-white/5 flex items-center gap-4 px-5 bg-[#07070f]">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-indigo-600 flex items-center justify-center">
            <Dna size={12} className="text-white" />
          </div>
          <span className="font-semibold text-white text-sm">GIAE</span>
        </div>
        <div className="w-px h-4 bg-white/10" />
        <p className="text-sm text-gray-300 truncate flex-1">{job.filename}</p>
        <span className="text-[10px] text-cyan-300 bg-cyan-400/10 border border-cyan-400/20 px-2 py-0.5 rounded-full mono shrink-0">
          shared report · read-only
        </span>
        <Link href="/" className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors shrink-0">
          Get GIAE →
        </Link>
      </div>

      {/* Three-pane layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Gene list */}
        <div className="w-60 shrink-0 border-r border-white/5 flex flex-col bg-[#0c0c18]">
          <div className="p-2.5 border-b border-white/5">
            <div className="relative">
              <Search size={11} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-600 pointer-events-none" />
              <input
                value={query} onChange={(e) => setQuery(e.target.value)}
                placeholder="Search genes…"
                className="w-full text-xs bg-white/4 border border-white/8 rounded-md pl-7 pr-2 py-1.5 text-gray-200 placeholder-gray-600 outline-none"
              />
            </div>
            <p className="text-[10px] text-gray-600 mono mt-2 px-0.5">{genes.length} / {job.total_genes} genes</p>
          </div>
          <div className="flex-1 overflow-y-auto p-1.5 space-y-px">
            {genes.map((g) => {
              const isSel    = selected?.id === g.id;
              const stripCol = g.is_dark ? "bg-amber-600"
                : g.confidence === "HIGH"     ? "bg-emerald-400"
                : g.confidence === "MODERATE" ? "bg-amber-500" : "bg-indigo-400";
              return (
                <button key={g.id} onClick={() => setSelected(g)}
                  className={cn("w-full text-left pl-2 pr-2.5 py-2 rounded-lg transition-all relative overflow-hidden",
                    isSel ? "bg-indigo-600/15 ring-1 ring-indigo-500/30" : "hover:bg-white/5")}
                >
                  <span className={cn("absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r", stripCol)} />
                  <div className="pl-2">
                    <p className={cn("text-xs font-medium truncate", isSel ? "text-white" : "text-gray-200")}>{g.name}</p>
                    <p className="text-[11px] text-gray-500 truncate">{g.normalized_product ?? g.function ?? (g.is_dark ? "Dark matter" : "—")}</p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Detail panel */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Genome track */}
          <div className="shrink-0 border-b border-white/5 px-4 py-3">
            <GenomeTrack genes={job.genes} selectedId={selected?.id ?? null} onSelect={setSelected} />
          </div>

          {/* Stats */}
          <div className="shrink-0 flex items-center gap-6 px-5 py-3 border-b border-white/5">
            {[
              { v: String(job.total_genes ?? 0),            l: "Genes",      c: "text-white"       },
              { v: String(job.high_confidence_count ?? 0),  l: "High conf",  c: "text-emerald-400" },
              { v: String(job.dark_count ?? 0),             l: "Dark matter",c: "text-amber-400"   },
              { v: `${successRate}%`,                        l: "Success",    c: "text-indigo-400"  },
            ].map((s) => (
              <div key={s.l} className="flex items-baseline gap-1.5">
                <span className={cn("text-lg font-bold mono", s.c)}>{s.v}</span>
                <span className="text-xs text-gray-500">{s.l}</span>
              </div>
            ))}
          </div>

          {/* Gene detail */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {selected ? (
              <>
                <div className="bg-[#0f0f1e] border border-white/6 rounded-xl p-5">
                  <div className="flex items-start justify-between gap-4 mb-3">
                    <div>
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <h3 className="text-base font-semibold text-white">{selected.name}</h3>
                        {selected.confidence && (
                          <span className={cn("text-xs px-2 py-0.5 rounded-full border",
                            selected.confidence === "HIGH"     ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                            : selected.confidence === "MODERATE" ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                            : "bg-indigo-500/10 text-indigo-400 border-indigo-500/20"
                          )}>{selected.confidence}</span>
                        )}
                        {selected.is_dark && (
                          <span className="text-xs px-2 py-0.5 rounded-full border bg-amber-500/10 text-amber-400 border-amber-500/20">DARK MATTER</span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500 mono">{selected.locus}</p>
                    </div>
                    {selected.score != null && (
                      <div className="text-right shrink-0">
                        <p className="text-xs text-gray-500 mb-0.5">Score</p>
                        <p className={cn("text-3xl font-bold mono",
                          selected.confidence === "HIGH" ? "text-emerald-400"
                          : selected.confidence === "MODERATE" ? "text-amber-400"
                          : "text-indigo-400"
                        )}>{selected.score.toFixed(2)}</p>
                      </div>
                    )}
                  </div>
                  {(selected.normalized_product || selected.function) && (
                    <p className="text-sm text-gray-300">{selected.normalized_product || selected.function}</p>
                  )}
                </div>

                <EvidenceLadder evidence={selected.evidence} isDark={selected.is_dark} />

                {!selected.is_dark && selected.score != null && (
                  <div className="grid lg:grid-cols-2 gap-4">
                    <ConfidenceComposition evidence={selected.evidence} score={selected.score} level={selected.confidence} />
                    {selected.competing_hypotheses?.length && selected.function && (
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
              </>
            ) : (
              <div className="flex items-center justify-center h-full">
                <p className="text-sm text-gray-500">Select a gene to inspect it</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
