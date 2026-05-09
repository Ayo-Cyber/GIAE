"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppNav } from "@/components/nav";
import { Search, Zap, FlaskConical } from "lucide-react";
import { api } from "@/lib/api";
import type { DarkGene } from "@/lib/types";

function StatusChip({ s }: { s: string }) {
  if (s === "Uncharacterized")
    return <span className="text-xs bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2 py-0.5 rounded-full">{s}</span>;
  return <span className="text-xs bg-white/5 text-gray-500 border border-white/8 px-2 py-0.5 rounded-full">{s}</span>;
}

export default function DatabasePage() {
  const [genes, setGenes] = useState<DarkGene[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listDarkGenes()
      .then(setGenes)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const filtered = genes.filter((g) => {
    const q = query.toLowerCase();
    return (
      !q ||
      g.name.toLowerCase().includes(q) ||
      g.locus.toLowerCase().includes(q) ||
      g.organism.toLowerCase().includes(q) ||
      g.id.toLowerCase().includes(q)
    );
  });

  return (
    <div className="min-h-screen bg-[#0a0a14]">
      <AppNav />
      <div className="pt-14 max-w-5xl mx-auto px-6 py-10">

        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <div className="flex items-center gap-2.5 mb-1">
              <h1 className="text-2xl font-semibold text-white">Dark Matter Database</h1>
              <span className="flex items-center gap-1 text-xs text-amber-400 bg-amber-400/10 border border-amber-400/20 px-2 py-0.5 rounded-full mono">
                <span className="w-1 h-1 rounded-full bg-amber-400 animate-pulse" />
                LIVE
              </span>
            </div>
            <p className="text-gray-400 text-sm">
              Unannotated genes discovered across all your interpretation jobs.
            </p>
          </div>
          <div className="text-right">
            <p className="text-3xl font-bold text-white mono">
              {loading ? "—" : genes.length}
            </p>
            <p className="text-xs text-gray-500">dark genes indexed</p>
          </div>
        </div>

        {/* Enterprise CTA */}
        <div className="bg-indigo-600/8 border border-indigo-500/20 rounded-xl px-5 py-4 flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Zap size={16} className="text-indigo-400 shrink-0" />
            <p className="text-sm text-gray-300">
              <span className="text-white font-medium">Enterprise plan</span> unlocks full API export, bulk queries, and private data enclaves.
            </p>
          </div>
          <button className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg font-medium transition-colors shrink-0 ml-4">
            Upgrade
          </button>
        </div>

        {/* Search */}
        <div className="flex items-center gap-3 bg-[#0f0f1e] border border-white/6 rounded-xl px-4 py-3 mb-4">
          <Search size={15} className="text-gray-600 shrink-0" />
          <input
            className="flex-1 bg-transparent text-sm text-gray-300 placeholder-gray-600 outline-none"
            placeholder="Search by gene name, locus, or organism..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        {/* Table */}
        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-[#0f0f1e] border border-white/6 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : genes.length === 0 ? (
          <div className="bg-[#0f0f1e] border border-white/6 rounded-2xl px-8 py-16 flex flex-col items-center text-center">
            <div className="w-12 h-12 rounded-xl bg-amber-600/10 border border-amber-500/20 flex items-center justify-center mb-4">
              <FlaskConical size={22} className="text-amber-400" />
            </div>
            <p className="text-white font-medium mb-1">No dark genes yet</p>
            <p className="text-sm text-gray-500 max-w-xs">
              Upload and run a genome from the{" "}
              <Link href="/dashboard" className="text-indigo-400 hover:underline">dashboard</Link>.
              {" "}Any genes with zero functional evidence will appear here.
            </p>
          </div>
        ) : (
          <div className="bg-[#0f0f1e] border border-white/6 rounded-xl overflow-hidden">
            <div className="grid grid-cols-4 text-xs text-gray-500 uppercase tracking-wider px-5 py-3 border-b border-white/5 bg-white/2">
              <span>Gene</span>
              <span>Locus</span>
              <span>Source file</span>
              <span>Status</span>
            </div>
            <div className="divide-y divide-white/4">
              {filtered.length === 0 ? (
                <p className="text-xs text-gray-600 px-5 py-6 text-center">No results match "{query}"</p>
              ) : (
                filtered.map((g) => (
                  <Link
                    key={g.id}
                    href={`/jobs/${g.job_id}`}
                    className="grid grid-cols-4 px-5 py-3.5 hover:bg-white/2 cursor-pointer transition-colors items-center"
                  >
                    <span className="text-xs font-medium text-gray-200">{g.name}</span>
                    <span className="mono text-xs text-indigo-400">{g.locus}</span>
                    <span className="text-xs text-gray-500 truncate">{g.organism}</span>
                    <StatusChip s="Uncharacterized" />
                  </Link>
                ))
              )}
            </div>
          </div>
        )}

        <p className="text-xs text-gray-600 text-center mt-4">
          {genes.length} entries from your jobs · Export and API access require Enterprise plan
        </p>
      </div>
    </div>
  );
}
