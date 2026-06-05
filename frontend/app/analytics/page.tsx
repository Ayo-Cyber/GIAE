"use client";

import { useEffect, useState } from "react";
import { AppNav } from "@/components/nav";
import { api } from "@/lib/api";
import type { Job } from "@/lib/types";
import { toast } from "sonner";
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell, CartesianGrid,
} from "recharts";
import { TrendingUp, Dna, FlaskConical, Clock, BarChart2 } from "lucide-react";

/* ── helpers ─────────────────────────────────────────────────────────── */

function weekKey(iso: string) {
  const d = new Date(iso);
  const jan1 = new Date(d.getFullYear(), 0, 1);
  const week = Math.ceil(((d.getTime() - jan1.getTime()) / 86400000 + jan1.getDay() + 1) / 7);
  return `W${String(week).padStart(2, "0")} ${d.getFullYear()}`;
}

const TOOLTIP_STYLE = {
  backgroundColor: "#0f0f1e",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: "8px",
  fontSize: "11px",
  color: "#e2e8f0",
};

/* ── stat card ───────────────────────────────────────────────────────── */

function Stat({ label, value, sub, color }: { label: string; value: string; sub: string; color: string }) {
  return (
    <div className="bg-[#0f0f1e] border border-white/6 rounded-xl p-5">
      <p className="text-xs text-gray-500 mb-2">{label}</p>
      <p className={`text-3xl font-bold mono ${color}`}>{value}</p>
      <p className="text-xs text-gray-600 mt-1">{sub}</p>
    </div>
  );
}

/* ── main page ───────────────────────────────────────────────────────── */

export default function AnalyticsPage() {
  const [jobs, setJobs]       = useState<Omit<Job, "genes">[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listJobs()
      .then(setJobs)
      .catch(() => toast.error("Could not load jobs."))
      .finally(() => setLoading(false));
  }, []);

  /* derived stats */
  const completed   = jobs.filter((j) => j.status === "COMPLETED");
  const totalGenes  = completed.reduce((a, j) => a + (j.total_genes ?? 0), 0);
  const totalDark   = completed.reduce((a, j) => a + (j.dark_count ?? 0), 0);
  const avgDarkPct  = completed.length
    ? Math.round((totalDark / Math.max(totalGenes, 1)) * 100)
    : 0;
  const avgTime     = completed.length
    ? Math.round(completed.reduce((a, j) => a + (j.processing_time_seconds ?? 0), 0) / completed.length)
    : 0;
  const avgHighConf = completed.length
    ? Math.round(
        completed.reduce(
          (a, j) => a + ((j.high_confidence_count ?? 0) / Math.max(j.total_genes ?? 1, 1)) * 100,
          0
        ) / completed.length
      )
    : 0;

  /* jobs per week */
  const weekMap = new Map<string, number>();
  for (const j of jobs) {
    if (!j.created_at) continue;
    const k = weekKey(j.created_at);
    weekMap.set(k, (weekMap.get(k) ?? 0) + 1);
  }
  const weekData = Array.from(weekMap.entries())
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([week, count]) => ({ week, count }));

  /* dark matter % per job */
  const darkData = completed
    .filter((j) => j.total_genes && j.total_genes > 0)
    .map((j) => ({
      name: j.filename.replace(/\.[^.]+$/, "").slice(0, 16),
      dark_pct: Math.round(((j.dark_count ?? 0) / (j.total_genes ?? 1)) * 100),
      high_pct: Math.round(((j.high_confidence_count ?? 0) / (j.total_genes ?? 1)) * 100),
    }))
    .slice(-12);

  /* processing time distribution */
  const timeData = completed
    .filter((j) => j.processing_time_seconds != null)
    .map((j) => ({
      name: j.filename.replace(/\.[^.]+$/, "").slice(0, 14),
      seconds: j.processing_time_seconds ?? 0,
    }))
    .sort((a, b) => a.seconds - b.seconds)
    .slice(-12);

  /* confidence breakdown across all jobs */
  const confData = [
    { label: "High",     value: completed.reduce((a, j) => a + (j.high_confidence_count ?? 0), 0),  color: "#34d399" },
    { label: "Dark",     value: totalDark,                                                           color: "#f59e0b" },
    { label: "Other",    value: Math.max(totalGenes - completed.reduce((a,j)=>a+(j.high_confidence_count??0),0) - totalDark, 0), color: "#818cf8" },
  ];

  return (
    <div className="min-h-screen bg-[#0a0a14]">
      <AppNav />
      <div className="app-shell">
        <div className="max-w-6xl mx-auto px-6 py-10">

          {/* Header */}
          <div className="flex items-center gap-3 mb-8">
            <div className="w-9 h-9 rounded-xl bg-indigo-600/15 border border-indigo-500/20 flex items-center justify-center">
              <BarChart2 size={18} className="text-indigo-400" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-white">Analytics</h1>
              <p className="text-sm text-gray-400">Trends across all your annotation jobs.</p>
            </div>
          </div>

          {loading ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
              {[1,2,3,4].map((i) => <div key={i} className="h-28 bg-[#0f0f1e] border border-white/6 rounded-xl animate-pulse" />)}
            </div>
          ) : (
            <>
              {/* Stat cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                <Stat label="Total jobs"        value={String(jobs.length)}    sub="all time"              color="text-white"       />
                <Stat label="Genes interpreted" value={String(totalGenes)}     sub="across completed jobs" color="text-indigo-400"  />
                <Stat label="Avg dark matter"   value={`${avgDarkPct}%`}       sub="of genes per job"      color="text-amber-400"   />
                <Stat label="Avg high-conf"     value={`${avgHighConf}%`}      sub="of genes per job"      color="text-emerald-400" />
              </div>

              {/* Row 1: jobs over time + confidence breakdown */}
              <div className="grid lg:grid-cols-3 gap-6 mb-6">
                <div className="lg:col-span-2 bg-[#0f0f1e] border border-white/6 rounded-xl p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <TrendingUp size={14} className="text-indigo-400" />
                    <p className="text-sm font-medium text-white">Jobs per week</p>
                  </div>
                  {weekData.length < 2 ? (
                    <p className="text-xs text-gray-600 py-8 text-center">Run more jobs to see trends.</p>
                  ) : (
                    <ResponsiveContainer width="100%" height={180}>
                      <LineChart data={weekData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                        <XAxis dataKey="week" tick={{ fontSize: 10, fill: "#6b7280" }} />
                        <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} allowDecimals={false} />
                        <Tooltip contentStyle={TOOLTIP_STYLE} />
                        <Line type="monotone" dataKey="count" stroke="#818cf8" strokeWidth={2} dot={{ r: 3, fill: "#818cf8" }} name="Jobs" />
                      </LineChart>
                    </ResponsiveContainer>
                  )}
                </div>

                <div className="bg-[#0f0f1e] border border-white/6 rounded-xl p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <Dna size={14} className="text-emerald-400" />
                    <p className="text-sm font-medium text-white">Gene confidence</p>
                  </div>
                  {totalGenes === 0 ? (
                    <p className="text-xs text-gray-600 py-8 text-center">No completed jobs yet.</p>
                  ) : (
                    <>
                      <div className="space-y-3 mt-2">
                        {confData.map((c) => (
                          <div key={c.label}>
                            <div className="flex justify-between text-xs mb-1">
                              <span className="text-gray-400">{c.label}</span>
                              <span className="mono text-gray-500">{c.value.toLocaleString()}</span>
                            </div>
                            <div className="h-1.5 bg-white/4 rounded-full overflow-hidden">
                              <div className="h-full rounded-full" style={{ width: `${Math.round((c.value / totalGenes) * 100)}%`, backgroundColor: c.color }} />
                            </div>
                          </div>
                        ))}
                      </div>
                      <p className="text-xs text-gray-600 mt-4 text-center">{totalGenes.toLocaleString()} genes total</p>
                    </>
                  )}
                </div>
              </div>

              {/* Row 2: dark matter % per job + processing time */}
              <div className="grid lg:grid-cols-2 gap-6 mb-6">
                <div className="bg-[#0f0f1e] border border-white/6 rounded-xl p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <FlaskConical size={14} className="text-amber-400" />
                    <p className="text-sm font-medium text-white">Dark matter % per job</p>
                    <span className="ml-auto text-xs text-gray-600">last 12</span>
                  </div>
                  {darkData.length === 0 ? (
                    <p className="text-xs text-gray-600 py-8 text-center">No completed jobs yet.</p>
                  ) : (
                    <ResponsiveContainer width="100%" height={180}>
                      <BarChart data={darkData} barGap={4}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                        <XAxis dataKey="name" tick={{ fontSize: 9, fill: "#6b7280" }} />
                        <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} unit="%" domain={[0, 100]} />
                        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: number) => [`${v}%`]} />
                        <Bar dataKey="high_pct" name="High conf" radius={[2, 2, 0, 0]}>
                          {darkData.map((_, i) => <Cell key={i} fill="#34d399" />)}
                        </Bar>
                        <Bar dataKey="dark_pct" name="Dark" radius={[2, 2, 0, 0]}>
                          {darkData.map((_, i) => <Cell key={i} fill="#f59e0b" />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </div>

                <div className="bg-[#0f0f1e] border border-white/6 rounded-xl p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <Clock size={14} className="text-cyan-400" />
                    <p className="text-sm font-medium text-white">Processing time</p>
                    <span className="ml-auto text-xs text-gray-500 mono">{avgTime}s avg</span>
                  </div>
                  {timeData.length === 0 ? (
                    <p className="text-xs text-gray-600 py-8 text-center">No completed jobs yet.</p>
                  ) : (
                    <ResponsiveContainer width="100%" height={180}>
                      <BarChart data={timeData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                        <XAxis dataKey="name" tick={{ fontSize: 9, fill: "#6b7280" }} />
                        <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} unit="s" />
                        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: number) => [`${v}s`, "Time"]} />
                        <Bar dataKey="seconds" name="Seconds" radius={[3, 3, 0, 0]}>
                          {timeData.map((_, i) => <Cell key={i} fill="#22d3ee" />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
