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

  return (
    <div className="min-h-screen bg-[#0a0a14]">
      <AppNav />
      <div className="pt-14 max-w-5xl mx-auto px-6 py-10">

        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-2xl font-semibold text-white mb-1">Jobs</h1>
            <p className="text-gray-400 text-sm">All genome interpretation runs.</p>
          </div>
          <div className="text-right">
            <p className="text-3xl font-bold text-white mono">
              {loading ? "—" : jobs.length}
            </p>
            <p className="text-xs text-gray-500">total jobs</p>
          </div>
        </div>

        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-14 bg-[#0f0f1e] border border-white/6 rounded-xl animate-pulse" />
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
              <Link href="/dashboard" className="text-indigo-400 hover:underline">dashboard</Link>{" "}
              to start an interpretation run.
            </p>
          </div>
        ) : (
          <div className="bg-[#0f0f1e] border border-white/6 rounded-xl overflow-hidden">
            <div className="grid grid-cols-5 text-xs text-gray-500 uppercase tracking-wider px-5 py-3 border-b border-white/5 bg-white/2">
              <span className="col-span-2">File</span>
              <span>Status</span>
              <span>Genes</span>
              <span>Actions</span>
            </div>
            <div className="divide-y divide-white/4">
              {jobs.map((job) => (
                <div
                  key={job.job_id}
                  className="grid grid-cols-5 px-5 py-3.5 hover:bg-white/2 transition-colors items-center"
                >
                  <Link
                    href={`/jobs/${job.job_id}`}
                    className="col-span-2 flex flex-col gap-0.5 group"
                  >
                    <span className="text-sm font-medium text-gray-200 group-hover:text-white transition-colors truncate">
                      {job.filename}
                    </span>
                    <span className="mono text-xs text-gray-600">{job.job_id.slice(0, 8)}…</span>
                  </Link>
                  <StatusBadge status={job.status} />
                  <span className={cn("text-xs mono", job.total_genes ? "text-gray-300" : "text-gray-600")}>
                    {job.total_genes != null ? (
                      <>
                        {job.total_genes}{" "}
                        {job.high_confidence_count != null && (
                          <span className="text-emerald-500">/ {job.high_confidence_count} high</span>
                        )}
                      </>
                    ) : "—"}
                  </span>
                  <div className="flex items-center gap-2">
                    <Link
                      href={`/jobs/${job.job_id}`}
                      className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
                    >
                      View →
                    </Link>
                    {job.report_url && (
                      <a
                        href={job.report_url}
                        target="_blank"
                        className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-200 transition-colors"
                      >
                        <Download size={11} /> Report
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
