"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { UploadZone } from "@/components/upload-zone";
import { ArrowRight, CheckCircle2, Clock, AlertCircle, Dna } from "lucide-react";
import { api } from "@/lib/api";
import type { Job } from "@/lib/types";

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
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-white mb-1">
          Good to see you, {firstName}
        </h1>
        <p className="text-gray-400 text-sm">Upload a genome to start a new interpretation job.</p>
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
          <div className="bg-[#0f0f1e] border border-white/6 rounded-2xl px-8 py-14 flex flex-col items-center text-center">
            <div className="w-12 h-12 rounded-xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center mb-4">
              <Dna size={22} className="text-indigo-400" />
            </div>
            <p className="text-white font-medium mb-1">No jobs yet</p>
            <p className="text-sm text-gray-500 max-w-xs">
              Upload a genome file above to run your first interpretation. Supports GenBank (.gb, .gbk) and FASTA (.fa, .fasta).
            </p>
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
