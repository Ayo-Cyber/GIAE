"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppNav } from "@/components/nav";
import { CheckCircle2, Clock, AlertCircle, Loader2, Download, FolderOpen } from "lucide-react";
import { api } from "@/lib/api";
import type { Job, JobStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

function StatusBadge({ status }: { status: JobStatus }) {
  if (status === "COMPLETED")
    return (
      <span className="flex items-center gap-1 text-xs text-emerald-400 bg-emerald-400/10 border border-emerald-400/20 px-2 py-0.5 rounded-full">
        <CheckCircle2 size={10} /> Completed
      </span>
    );
  if (status === "FAILED")
    return (
      <span className="flex items-center gap-1 text-xs text-red-400 bg-red-400/10 border border-red-400/20 px-2 py-0.5 rounded-full">
        <AlertCircle size={10} /> Failed
      </span>
    );
  if (status === "RUNNING")
    return (
      <span className="flex items-center gap-1 text-xs text-indigo-400 bg-indigo-400/10 border border-indigo-400/20 px-2 py-0.5 rounded-full">
        <Loader2 size={10} className="animate-spin" /> Running
      </span>
    );
  if (status === "CANCELLED")
    return (
      <span className="flex items-center gap-1 text-xs text-gray-400 bg-gray-400/10 border border-gray-400/20 px-2 py-0.5 rounded-full">
        <AlertCircle size={10} /> Cancelled
      </span>
    );
  return (
    <span className="flex items-center gap-1 text-xs text-amber-400 bg-amber-400/10 border border-amber-400/20 px-2 py-0.5 rounded-full">
      <Clock size={10} /> Pending
    </span>
  );
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Omit<Job, "genes">[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listJobs()
      .then(setJobs)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Grid template: File grows · Status fits · Genes fits · Actions right-aligned
  const cols =
    "grid grid-cols-[minmax(0,1fr)_140px_160px_140px] gap-x-6 items-center";

  return (
    <div className="min-h-screen bg-[#0a0a14]">
      <AppNav />
      <div className="pt-14 max-w-5xl mx-auto px-6 py-10">
        {/* Header */}
        <div className="flex items-start justify-between mb-8 gap-6">
          <div>
            <h1 className="text-2xl font-semibold text-white mb-1 tracking-tight">Jobs</h1>
            <p className="text-gray-400 text-sm">All genome interpretation runs.</p>
          </div>
          <div className="text-right shrink-0">
            <p className="text-3xl font-bold text-white mono tabular-nums leading-none">
              {loading ? "—" : jobs.length}
            </p>
            <p className="text-xs text-gray-500 mt-1.5">total jobs</p>
          </div>
        </div>

        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-16 bg-[#0f0f1e] border border-white/6 rounded-xl animate-pulse"
              />
            ))}
          </div>
        ) : jobs.length === 0 ? (
          <div className="bg-[#0f0f1e] border border-white/6 rounded-2xl px-8 py-16 flex flex-col items-center text-center">
            <div className="w-12 h-12 rounded-xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center mb-4">
              <FolderOpen size={22} className="text-indigo-400" />
            </div>
            <p className="text-white font-medium mb-1">No jobs yet</p>
            <p className="text-sm text-gray-500 max-w-xs">
              Upload a genome from the{" "}
              <Link href="/dashboard" className="text-indigo-400 hover:underline">
                dashboard
              </Link>{" "}
              to start an interpretation run.
            </p>
          </div>
        ) : (
          <div className="bg-[#0f0f1e] border border-white/6 rounded-xl overflow-hidden">
            {/* Header row */}
            <div
              className={cn(
                cols,
                "text-[11px] text-gray-500 uppercase tracking-wider font-medium px-6 py-3 border-b border-white/5 bg-white/2"
              )}
            >
              <span>File</span>
              <span>Status</span>
              <span>Genes</span>
              <span className="text-right">Actions</span>
            </div>

            {/* Rows */}
            <div className="divide-y divide-white/[0.04]">
              {jobs.map((job) => (
                <Link
                  key={job.job_id}
                  href={`/jobs/${job.job_id}`}
                  className={cn(
                    cols,
                    "px-6 py-4 hover:bg-white/[0.025] transition-colors group"
                  )}
                >
                  {/* File */}
                  <div className="min-w-0 flex flex-col gap-0.5">
                    <span className="text-sm font-medium text-gray-200 group-hover:text-white transition-colors truncate">
                      {job.filename}
                    </span>
                    <span className="mono text-[11px] text-gray-600">
                      {job.job_id.slice(0, 8)}…
                    </span>
                  </div>

                  {/* Status */}
                  <div>
                    <StatusBadge status={job.status} />
                  </div>

                  {/* Genes */}
                  <div className="text-xs mono tabular-nums">
                    {job.total_genes != null ? (
                      <span className="text-gray-300">
                        {job.total_genes}
                        {job.high_confidence_count != null && (
                          <>
                            <span className="text-gray-600"> · </span>
                            <span className="text-emerald-400">
                              {job.high_confidence_count} high
                            </span>
                          </>
                        )}
                      </span>
                    ) : (
                      <span className="text-gray-600">—</span>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center justify-end gap-3">
                    <span className="text-xs text-indigo-400 group-hover:text-indigo-300 transition-colors">
                      View →
                    </span>
                    {job.report_url && (
                      <a
                        href={job.report_url}
                        target="_blank"
                        onClick={(e) => e.stopPropagation()}
                        className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-200 transition-colors"
                      >
                        <Download size={11} /> Report
                      </a>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
