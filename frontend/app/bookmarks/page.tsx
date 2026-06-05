"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppNav } from "@/components/nav";
import { Bookmark, getBookmarks, removeBookmark } from "@/lib/bookmarks";
import { Bookmark as BookmarkIcon, Trash2, ExternalLink, Dna } from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

function ConfidenceDot({ level }: { level: string | null }) {
  const color =
    level === "HIGH"     ? "bg-emerald-400" :
    level === "MODERATE" ? "bg-amber-400"   :
    level === "LOW"      ? "bg-indigo-400"  : "bg-gray-600";
  return <span className={cn("w-2 h-2 rounded-full shrink-0", color)} />;
}

export default function BookmarksPage() {
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);

  useEffect(() => {
    setBookmarks(getBookmarks());
  }, []);

  const remove = (geneId: string, name: string) => {
    removeBookmark(geneId);
    setBookmarks(getBookmarks());
    toast.success(`Removed "${name}" from bookmarks.`);
  };

  const byJob = bookmarks.reduce<Record<string, Bookmark[]>>((acc, b) => {
    (acc[b.jobId] ??= []).push(b);
    return acc;
  }, {});

  return (
    <div className="min-h-screen bg-[#0a0a14]">
      <AppNav />
      <div className="app-shell">
        <div className="max-w-4xl mx-auto px-6 py-10">

          {/* Header */}
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
                <BookmarkIcon size={17} className="text-amber-400" />
              </div>
              <div>
                <h1 className="text-2xl font-semibold text-white">Bookmarks</h1>
                <p className="text-sm text-gray-400">Starred genes saved across all jobs.</p>
              </div>
            </div>
            <span className="mono text-xs text-gray-500 bg-white/4 border border-white/6 px-3 py-1.5 rounded-full">
              {bookmarks.length} saved
            </span>
          </div>

          {bookmarks.length === 0 ? (
            <div className="bg-[#0f0f1e] border border-white/6 rounded-2xl px-8 py-16 flex flex-col items-center text-center">
              <div className="w-12 h-12 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center mb-4">
                <BookmarkIcon size={22} className="text-amber-400" />
              </div>
              <p className="text-white font-medium mb-1">No bookmarks yet</p>
              <p className="text-sm text-gray-500 max-w-xs">
                Open any job, select a gene, and click the bookmark icon to save it here for follow-up.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {Object.entries(byJob).map(([jobId, genes]) => (
                <div key={jobId} className="bg-[#0f0f1e] border border-white/6 rounded-xl overflow-hidden">
                  {/* Job header */}
                  <div className="flex items-center gap-3 px-5 py-3 border-b border-white/5 bg-white/[0.02]">
                    <Dna size={13} className="text-indigo-400 shrink-0" />
                    <p className="text-xs font-medium text-gray-300 flex-1 truncate">
                      {genes[0].jobFilename}
                    </p>
                    <Link
                      href={`/jobs/${jobId}`}
                      className="flex items-center gap-1 text-[11px] text-indigo-400 hover:text-indigo-300 transition-colors shrink-0"
                    >
                      Open job <ExternalLink size={10} />
                    </Link>
                  </div>

                  {/* Gene rows */}
                  <div className="divide-y divide-white/[0.04]">
                    {genes.map((b) => (
                      <div key={b.geneId} className="flex items-center gap-4 px-5 py-3.5 group">
                        <ConfidenceDot level={b.is_dark ? null : b.confidence} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5">
                            <span className="text-sm font-medium text-gray-200">{b.geneName}</span>
                            {b.is_dark && (
                              <span className="text-[10px] text-amber-400 bg-amber-500/10 border border-amber-500/20 px-1.5 py-0.5 rounded-full">dark</span>
                            )}
                            {b.confidence && !b.is_dark && (
                              <span className="text-[10px] text-gray-500 capitalize">{b.confidence.toLowerCase()}</span>
                            )}
                          </div>
                          <p className="text-xs text-gray-500 truncate">
                            {b.function ?? "Unannotated"} · <span className="mono text-gray-600">{b.locus}</span>
                          </p>
                        </div>
                        {b.score != null && (
                          <span className="mono text-sm font-semibold text-gray-400 shrink-0">{b.score.toFixed(2)}</span>
                        )}
                        <Link
                          href={`/jobs/${b.jobId}`}
                          className="text-[11px] text-indigo-400 hover:text-indigo-300 transition-colors shrink-0 opacity-0 group-hover:opacity-100"
                        >
                          View →
                        </Link>
                        <button
                          onClick={() => remove(b.geneId, b.geneName)}
                          className="p-1.5 rounded-lg text-gray-700 hover:text-red-400 hover:bg-red-500/10 transition-colors shrink-0 opacity-0 group-hover:opacity-100"
                          title="Remove bookmark"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
