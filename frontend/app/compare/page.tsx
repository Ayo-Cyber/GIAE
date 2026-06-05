"use client";

import { useEffect, useState } from "react";
import { AppNav } from "@/components/nav";
import { api } from "@/lib/api";
import type { Job, GeneRow } from "@/lib/types";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  GitCompare, ChevronDown, CheckCircle2, AlertCircle,
  ArrowRight, Minus,
} from "lucide-react";

type DiffStatus = "shared" | "only-a" | "only-b" | "changed";

interface GeneDiff {
  locus: string;
  name: string;
  status: DiffStatus;
  geneA?: GeneRow;
  geneB?: GeneRow;
  confChanged?: boolean;
  darkChanged?: boolean;
}

function diffJobs(a: Job, b: Job): GeneDiff[] {
  const byLocus = (genes: GeneRow[]) =>
    genes.reduce<Record<string, GeneRow>>((m, g) => { m[g.locus] = g; return m; }, {});

  const mapA = byLocus(a.genes);
  const mapB = byLocus(b.genes);
  const allLoci = Array.from(new Set([...Object.keys(mapA), ...Object.keys(mapB)]));
  const diffs: GeneDiff[] = [];

  for (const locus of allLoci) {
    const ga = mapA[locus];
    const gb = mapB[locus];

    if (ga && gb) {
      const confChanged = ga.confidence !== gb.confidence;
      const darkChanged = ga.is_dark !== gb.is_dark;
      diffs.push({
        locus,
        name: gb.name ?? ga.name,
        status: confChanged || darkChanged ? "changed" : "shared",
        geneA: ga,
        geneB: gb,
        confChanged,
        darkChanged,
      });
    } else if (ga) {
      diffs.push({ locus, name: ga.name, status: "only-a", geneA: ga });
    } else if (gb) {
      diffs.push({ locus, name: gb.name, status: "only-b", geneB: gb });
    }
  }

  return diffs.sort((a, b) => {
    const order: Record<DiffStatus, number> = { changed: 0, "only-a": 1, "only-b": 2, shared: 3 };
    return order[a.status] - order[b.status];
  });
}

function ConfBadge({ level, isDark }: { level: string | null; isDark: boolean }) {
  if (isDark)
    return <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">dark</span>;
  if (!level) return <span className="text-[10px] text-gray-600">—</span>;
  const cls =
    level === "HIGH"     ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" :
    level === "MODERATE" ? "bg-amber-500/10 text-amber-400 border-amber-500/20" :
                           "bg-indigo-500/10 text-indigo-400 border-indigo-500/20";
  return <span className={cn("text-[10px] px-1.5 py-0.5 rounded border", cls)}>{level}</span>;
}

function JobPicker({
  label, job, jobs, loading, onChange,
}: {
  label: string;
  job: Job | null;
  jobs: Omit<Job, "genes">[];
  loading: boolean;
  onChange: (id: string) => void;
}) {
  return (
    <div className="flex-1 min-w-0">
      <p className="text-xs text-gray-500 mb-2">{label}</p>
      <div className="relative">
        <select
          value={job?.job_id ?? ""}
          onChange={(e) => onChange(e.target.value)}
          disabled={loading}
          className="w-full bg-[#0f0f1e] border border-white/8 rounded-xl px-4 py-3 text-sm text-gray-200 outline-none appearance-none cursor-pointer hover:border-indigo-500/40 transition-colors"
        >
          <option value="" disabled>Select a completed job…</option>
          {jobs.filter((j) => j.status === "COMPLETED").map((j) => (
            <option key={j.job_id} value={j.job_id}>{j.filename}</option>
          ))}
        </select>
        <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
      </div>
      {job && (
        <p className="text-xs text-gray-600 mono mt-1.5 px-1">
          {job.total_genes} genes · {job.dark_count} dark · {job.high_confidence_count} high
        </p>
      )}
    </div>
  );
}

export default function ComparePage() {
  const [allJobs, setAllJobs]   = useState<Omit<Job, "genes">[]>([]);
  const [jobA, setJobA]         = useState<Job | null>(null);
  const [jobB, setJobB]         = useState<Job | null>(null);
  const [loadingJobs, setLoadingJobs]   = useState(true);
  const [loadingA, setLoadingA] = useState(false);
  const [loadingB, setLoadingB] = useState(false);
  const [filter, setFilter]     = useState<DiffStatus | "all">("all");

  useEffect(() => {
    api.listJobs()
      .then(setAllJobs)
      .catch(() => toast.error("Could not load jobs."))
      .finally(() => setLoadingJobs(false));
  }, []);

  const pickJob = async (id: string, side: "a" | "b") => {
    if (side === "a") setLoadingA(true); else setLoadingB(true);
    try {
      const j = await api.getJob(id);
      if (side === "a") setJobA(j); else setJobB(j);
    } catch {
      toast.error("Could not load job.");
    } finally {
      if (side === "a") setLoadingA(false); else setLoadingB(false);
    }
  };

  const diffs = jobA && jobB ? diffJobs(jobA, jobB) : [];
  const filtered = filter === "all" ? diffs : diffs.filter((d) => d.status === filter);

  const counts = {
    changed: diffs.filter((d) => d.status === "changed").length,
    "only-a": diffs.filter((d) => d.status === "only-a").length,
    "only-b": diffs.filter((d) => d.status === "only-b").length,
    shared:   diffs.filter((d) => d.status === "shared").length,
  };

  return (
    <div className="min-h-screen bg-[#0a0a14]">
      <AppNav />
      <div className="app-shell">
        <div className="max-w-6xl mx-auto px-6 py-10">

          {/* Header */}
          <div className="flex items-center gap-3 mb-8">
            <div className="w-9 h-9 rounded-xl bg-indigo-600/15 border border-indigo-500/20 flex items-center justify-center">
              <GitCompare size={17} className="text-indigo-400" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-white">Job Comparison</h1>
              <p className="text-sm text-gray-400">Diff two completed annotation runs gene-by-gene.</p>
            </div>
          </div>

          {/* Job selectors */}
          <div className="flex items-end gap-4 mb-8">
            <JobPicker label="Job A (baseline)" job={jobA} jobs={allJobs} loading={loadingJobs || loadingA} onChange={(id) => pickJob(id, "a")} />
            <div className="shrink-0 mb-3">
              <ArrowRight size={18} className="text-gray-600" />
            </div>
            <JobPicker label="Job B (comparison)" job={jobB} jobs={allJobs} loading={loadingJobs || loadingB} onChange={(id) => pickJob(id, "b")} />
          </div>

          {/* Results */}
          {jobA && jobB && (
            <>
              {/* Summary cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
                {[
                  { label: "Changed",    count: counts.changed,    color: "text-amber-400",   bg: "bg-amber-500/5  border-amber-500/15",  key: "changed"  },
                  { label: "Only in A",  count: counts["only-a"],  color: "text-red-400",     bg: "bg-red-500/5    border-red-500/15",     key: "only-a"   },
                  { label: "Only in B",  count: counts["only-b"],  color: "text-emerald-400", bg: "bg-emerald-500/5 border-emerald-500/15", key: "only-b"  },
                  { label: "Unchanged",  count: counts.shared,     color: "text-gray-400",    bg: "bg-white/[0.03] border-white/6",        key: "shared"   },
                ].map(({ label, count, color, bg, key }) => (
                  <button
                    key={key}
                    onClick={() => setFilter(filter === key ? "all" : key as DiffStatus)}
                    className={cn(
                      "rounded-xl border px-4 py-3 text-left transition-all",
                      bg,
                      filter === key && "ring-1 ring-indigo-500/40"
                    )}
                  >
                    <p className={cn("text-2xl font-bold mono", color)}>{count}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{label}</p>
                  </button>
                ))}
              </div>

              {/* Diff table */}
              <div className="bg-[#0f0f1e] border border-white/6 rounded-xl overflow-hidden">
                <div className="grid grid-cols-[1fr_1fr_1fr_1fr] text-[10px] text-gray-500 uppercase tracking-wider px-5 py-3 border-b border-white/5 bg-white/[0.02]">
                  <span>Locus / Gene</span>
                  <span>Confidence A</span>
                  <span>Confidence B</span>
                  <span>Status</span>
                </div>
                <div className="divide-y divide-white/[0.04] max-h-[60vh] overflow-y-auto">
                  {filtered.length === 0 ? (
                    <p className="text-xs text-gray-600 px-5 py-8 text-center">No genes match this filter.</p>
                  ) : filtered.map((d) => (
                    <div key={d.locus} className="grid grid-cols-[1fr_1fr_1fr_1fr] px-5 py-3 items-center hover:bg-white/[0.02] transition-colors">
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-gray-200 truncate">{d.name}</p>
                        <p className="text-[10px] mono text-gray-600 truncate">{d.locus}</p>
                      </div>
                      <div>
                        {d.geneA
                          ? <ConfBadge level={d.geneA.confidence} isDark={d.geneA.is_dark} />
                          : <Minus size={12} className="text-gray-700" />}
                      </div>
                      <div>
                        {d.geneB
                          ? <ConfBadge level={d.geneB.confidence} isDark={d.geneB.is_dark} />
                          : <Minus size={12} className="text-gray-700" />}
                      </div>
                      <div>
                        {d.status === "changed"  && <span className="flex items-center gap-1 text-[10px] text-amber-400"><AlertCircle size={10} /> Changed</span>}
                        {d.status === "only-a"   && <span className="text-[10px] text-red-400">Only in A</span>}
                        {d.status === "only-b"   && <span className="text-[10px] text-emerald-400">Only in B</span>}
                        {d.status === "shared"   && <span className="flex items-center gap-1 text-[10px] text-gray-600"><CheckCircle2 size={10} /> Same</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <p className="text-xs text-gray-600 text-center mt-3">{filtered.length} genes shown</p>
            </>
          )}

          {(!jobA || !jobB) && !loadingA && !loadingB && (
            <div className="bg-[#0f0f1e] border border-white/6 rounded-2xl px-8 py-16 flex flex-col items-center text-center">
              <GitCompare size={28} className="text-gray-700 mb-4" />
              <p className="text-white font-medium mb-1">Select two jobs to compare</p>
              <p className="text-sm text-gray-500 max-w-xs">
                Choose a baseline and a comparison job above to see a gene-level diff.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
