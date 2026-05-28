"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { UploadZone } from "@/components/upload-zone";
import { ArrowRight, CheckCircle2, Clock, AlertCircle, Dna, PlayCircle, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import type { Job } from "@/lib/types";
import { DEMO_JOB_ID } from "@/data/demo-data";

function StatusBadge({ status }: { status: string }) {
  if (status === "COMPLETED")
    return (
      <span className="inline-flex items-center gap-1.5 text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2.5 py-1 rounded-full">
        <CheckCircle2 size={10} /> Completed
      </span>
    );
  if (status === "RUNNING" || status === "PENDING")
    return (
      <span className="inline-flex items-center gap-1.5 text-xs bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2.5 py-1 rounded-full">
        <Clock size={10} className="animate-spin" /> Running
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1.5 text-xs bg-red-500/10 text-red-400 border border-red-500/20 px-2.5 py-1 rounded-full">
      <AlertCircle size={10} /> Failed
    </span>
  );
}

export default function DashboardPage() {
  const { data: session } = useSession();
  const [jobs, setJobs] = useState<Omit<Job, "genes">[]>([]);
  const [loading, setLoading] = useState(true);

  const firstName =
    (session?.user as { firstName?: string })?.firstName ||
    session?.user?.name?.split(" ")[0] ||
    "there";

  useEffect(() => {
    api
      .listJobs()
      .then(setJobs)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Compute stats from real jobs
  const completedJobs = jobs.filter((j) => j.status === "COMPLETED");
  const totalGenes = completedJobs.reduce((a, j) => a + (j.total_genes ?? 0), 0);
  const totalDark = completedJobs.reduce((a, j) => a + (j.dark_count ?? 0), 0);
  const avgHighConf =
    completedJobs.length > 0
      ? Math.round(
          completedJobs.reduce(
            (a, j) =>
              a +
              ((j.high_confidence_count ?? 0) / Math.max(j.total_genes ?? 1, 1)) * 100,
            0
          ) / completedJobs.length
        )
      : 0;

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      {/* Header */}
      <div className="mb-8 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="inline-flex items-center gap-1.5 text-xs text-cyan-300 bg-cyan-400/10 border border-cyan-400/20 px-2.5 py-1 rounded-full mb-3">
            <Sparkles size={12} />
            Explainable genome annotation
          </div>
          <h1 className="text-2xl font-semibold text-white mb-1">
            Good to see you, {firstName}
          </h1>
          <p className="text-gray-400 text-sm">Upload a genome or open the sample report to see GIAE's reasoning in action.</p>
        </div>
        <Link
          href={`/jobs/${DEMO_JOB_ID}`}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/15 border border-cyan-400/25 px-4 py-2.5 text-sm font-medium text-cyan-200 transition-colors"
        >
          <PlayCircle size={15} />
          Load sample report
        </Link>
      </div>

      {/* Upload */}
      <div className="mb-8">
        <UploadZone />
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {[
          { label: "Jobs run", value: String(jobs.length), sub: "total", color: "text-white" },
          { label: "Genes interpreted", value: String(totalGenes), sub: "across all jobs", color: "text-indigo-400" },
          { label: "Dark matter", value: String(totalDark), sub: "unannotated genes", color: "text-amber-400" },
          {
            label: "High confidence",
            value: completedJobs.length > 0 ? `${avgHighConf}%` : "—",
            sub: "average across jobs",
            color: "text-emerald-400",
          },
        ].map((s) => (
          <div key={s.label} className="bg-[#0f0f1e] border border-white/6 rounded-xl p-4">
            <p className="text-gray-500 text-xs mb-2">{s.label}</p>
            <p className={`text-2xl font-semibold ${s.color}`}>{s.value}</p>
            <p className="text-xs text-gray-600 mt-1">{s.sub}</p>
          </div>
        ))}
      </div>

      {/* Recent jobs */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-300">Recent jobs</h2>
        </div>

        {loading ? (
          <div className="space-y-2">
            {[1, 2].map((i) => (
              <div key={i} className="h-16 bg-[#0f0f1e] border border-white/6 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : jobs.length === 0 ? (
          <div className="bg-[#0f0f1e] border border-white/6 rounded-2xl px-8 py-12 grid gap-8 lg:grid-cols-[1fr_320px] lg:items-center">
            <div className="text-center lg:text-left">
              <div className="w-12 h-12 rounded-xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center mb-4 mx-auto lg:mx-0">
                <Dna size={22} className="text-indigo-400" />
              </div>
              <p className="text-white font-medium mb-1">No jobs yet</p>
              <p className="text-sm text-gray-500 max-w-md mx-auto lg:mx-0">
                Upload a genome file above to run your first interpretation, or open the curated lambda phage sample for an instant demo.
              </p>
            </div>
            <div className="rounded-xl border border-cyan-400/15 bg-cyan-400/5 p-4">
              <p className="text-xs uppercase tracking-wider text-cyan-300 mb-2">Stage-ready demo</p>
              <p className="text-sm text-gray-300 mb-4">
                Lambda phage report with gene map, evidence ladder, dark-matter calls, and reasoning chain.
              </p>
              <Link
                href={`/jobs/${DEMO_JOB_ID}`}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-cyan-500/15 hover:bg-cyan-500/20 border border-cyan-400/25 px-4 py-2 text-sm font-medium text-cyan-100 transition-colors"
              >
                <PlayCircle size={15} />
                Open sample
              </Link>
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            {jobs.map((job) => (
              <Link
                key={job.job_id}
                href={`/jobs/${job.job_id}`}
                className="flex items-center justify-between bg-[#0f0f1e] border border-white/6 hover:border-indigo-500/25 rounded-xl px-5 py-4 transition-colors group"
              >
                <div className="flex items-center gap-4">
                  <div
                    className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                      job.status === "COMPLETED"
                        ? "bg-emerald-500/10 border border-emerald-500/20"
                        : "bg-amber-500/10 border border-amber-500/20"
                    }`}
                  >
                    {job.status === "COMPLETED" ? (
                      <CheckCircle2 size={14} className="text-emerald-400" />
                    ) : (
                      <Clock size={14} className="text-amber-400 animate-spin" />
                    )}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-white">{job.filename}</p>
                    <p className="text-xs text-gray-500 mono">
                      {job.total_genes != null
                        ? `${job.total_genes} genes · ${job.processing_time_seconds}s`
                        : job.status}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-5">
                  {job.high_confidence_count != null && (
                    <div className="hidden md:block text-right">
                      <p className="text-xs text-gray-500">High conf.</p>
                      <p className="text-sm font-semibold text-emerald-400">{job.high_confidence_count}</p>
                    </div>
                  )}
                  {job.dark_count != null && (
                    <div className="hidden md:block text-right">
                      <p className="text-xs text-gray-500">Dark matter</p>
                      <p className="text-sm font-semibold text-amber-400">{job.dark_count}</p>
                    </div>
                  )}
                  <StatusBadge status={job.status} />
                  <ArrowRight size={14} className="text-gray-600 group-hover:text-gray-400 transition-colors" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
