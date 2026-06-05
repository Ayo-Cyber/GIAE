"use client";

import { useEffect, useState } from "react";
import { AppNav } from "@/components/nav";
import { api } from "@/lib/api";
import type { WatchlistEntry } from "@/lib/types";
import { toast } from "sonner";
import { Eye, Trash2, Telescope } from "lucide-react";

export default function WatchlistPage() {
  const [entries, setEntries] = useState<WatchlistEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getWatchlist()
      .then(setEntries)
      .catch(() => toast.error("Could not load watchlist."))
      .finally(() => setLoading(false));
  }, []);

  const remove = async (locus: string, name: string) => {
    try {
      await api.removeFromWatchlist(locus);
      setEntries((prev) => prev.filter((e) => e.locus !== locus));
      toast.success(`Stopped watching "${name}".`);
    } catch {
      toast.error("Failed to remove from watchlist.");
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a14]">
      <AppNav />
      <div className="app-shell">
        <div className="max-w-3xl mx-auto px-6 py-10">

          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-indigo-600/15 border border-indigo-500/20 flex items-center justify-center">
                <Telescope size={17} className="text-indigo-400" />
              </div>
              <div>
                <h1 className="text-2xl font-semibold text-white">Watchlist</h1>
                <p className="text-sm text-gray-400">Dark genes you're tracking for future annotation.</p>
              </div>
            </div>
            <span className="mono text-xs text-gray-500 bg-white/4 border border-white/6 px-3 py-1.5 rounded-full">
              {entries.length} watching
            </span>
          </div>

          {loading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-14 bg-[#0f0f1e] border border-white/6 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : entries.length === 0 ? (
            <div className="bg-[#0f0f1e] border border-white/6 rounded-2xl px-8 py-16 flex flex-col items-center text-center">
              <div className="w-12 h-12 rounded-xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center mb-4">
                <Telescope size={22} className="text-indigo-400" />
              </div>
              <p className="text-white font-medium mb-1">No genes on watchlist</p>
              <p className="text-sm text-gray-500 max-w-xs">
                Click the <span className="text-indigo-400">Watch</span> button on any dark matter gene to get
                notified when a future job annotates it.
              </p>
            </div>
          ) : (
            <div className="bg-[#0f0f1e] border border-white/6 rounded-xl overflow-hidden">
              <div className="grid grid-cols-[1fr_auto_auto] text-[10px] text-gray-500 uppercase tracking-wider px-5 py-3 border-b border-white/5 bg-white/[0.02]">
                <span>Gene / Locus</span>
                <span>Watching since</span>
                <span />
              </div>
              <div className="divide-y divide-white/[0.04]">
                {entries.map((e) => (
                  <div key={e.id} className="grid grid-cols-[1fr_auto_auto] items-center px-5 py-3.5 gap-4 group hover:bg-white/[0.02] transition-colors">
                    <div>
                      <p className="text-sm font-medium text-gray-200">{e.gene_name}</p>
                      <p className="text-[11px] mono text-indigo-400">{e.locus}</p>
                    </div>
                    <p className="text-xs text-gray-500 mono">
                      {new Date(e.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                    </p>
                    <button
                      onClick={() => remove(e.locus, e.gene_name)}
                      className="p-1.5 rounded-lg text-gray-700 hover:text-red-400 hover:bg-red-500/10 transition-colors opacity-0 group-hover:opacity-100"
                      title="Stop watching"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <p className="text-xs text-gray-600 text-center mt-6 flex items-center justify-center gap-1.5">
            <Eye size={11} />
            You'll see a notification when any future job annotates a watched gene.
          </p>
        </div>
      </div>
    </div>
  );
}
