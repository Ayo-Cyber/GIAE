"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useRouter } from "next/navigation";
import { Upload, Loader2, CheckCircle2, XCircle, FileText, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { toast } from "sonner";

type FileStatus = "pending" | "uploading" | "done" | "error";

interface QueueEntry {
  file: File;
  status: FileStatus;
  jobId?: string;
  error?: string;
}

export function UploadZone() {
  const router = useRouter();
  const [queue, setQueue] = useState<QueueEntry[]>([]);
  const [running, setRunning] = useState(false);

  const updateEntry = (name: string, patch: Partial<QueueEntry>) =>
    setQueue((prev) => prev.map((e) => e.file.name === name ? { ...e, ...patch } : e));

  const processQueue = useCallback(async (entries: QueueEntry[]) => {
    setRunning(true);
    let lastJobId: string | undefined;

    for (const entry of entries) {
      updateEntry(entry.file.name, { status: "uploading" });
      try {
        const result = await api.createJob(entry.file);
        if ("error" in result) {
          const msg = (result as { error: string }).error;
          updateEntry(entry.file.name, { status: "error", error: msg });
          toast.error(`${entry.file.name}: ${msg}`);
        } else {
          updateEntry(entry.file.name, { status: "done", jobId: result.job_id });
          lastJobId = result.job_id;
        }
      } catch {
        const msg = "Upload failed.";
        updateEntry(entry.file.name, { status: "error", error: msg });
        toast.error(`${entry.file.name}: ${msg}`);
      }
    }

    setRunning(false);

    // If only one file, navigate directly to its job
    if (entries.length === 1 && lastJobId) {
      router.push(`/jobs/${lastJobId}`);
    } else if (entries.length > 1) {
      toast.success(`${entries.length} jobs queued — see Jobs for progress.`);
      setTimeout(() => router.push("/jobs"), 1200);
    }
  }, [router]);

  const onDrop = useCallback((accepted: File[]) => {
    if (!accepted.length) return;
    const newEntries: QueueEntry[] = accepted.map((f) => ({ file: f, status: "pending" }));
    setQueue(newEntries);
    processQueue(newEntries);
  }, [processQueue]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "chemical/x-genbank": [".gb", ".gbk"],
      "text/plain":          [".fasta", ".fa", ".fna"],
      "application/octet-stream": [".gb", ".gbk", ".fasta", ".fa"],
    },
    multiple: true,
    disabled: running,
  });

  const clear = () => { if (!running) setQueue([]); };

  const statusIcon = (s: FileStatus) => {
    if (s === "uploading") return <Loader2 size={13} className="text-indigo-400 animate-spin" />;
    if (s === "done")      return <CheckCircle2 size={13} className="text-emerald-400" />;
    if (s === "error")     return <XCircle size={13} className="text-red-400" />;
    return <FileText size={13} className="text-gray-500" />;
  };

  return (
    <div className="space-y-3">
      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={cn(
          "border border-dashed rounded-2xl px-8 py-10 text-center cursor-pointer transition-all",
          isDragActive
            ? "border-indigo-500/70 bg-indigo-500/5"
            : "border-white/10 hover:border-indigo-500/40 hover:bg-indigo-500/3",
          running && "pointer-events-none opacity-60"
        )}
      >
        <input {...getInputProps()} />
        <div className={cn(
          "w-12 h-12 rounded-2xl flex items-center justify-center mx-auto mb-4 transition-colors",
          isDragActive ? "bg-indigo-600/30 border border-indigo-500/50" : "bg-indigo-600/15 border border-indigo-500/25"
        )}>
          {running ? <Loader2 size={20} className="text-indigo-400 animate-spin" /> : <Upload size={20} className="text-indigo-400" />}
        </div>
        <p className="text-white font-medium mb-1">
          {isDragActive ? "Drop files here" : running ? "Uploading…" : "Drop genome files here"}
        </p>
        <p className="text-gray-500 text-sm mb-4">
          Supports{" "}
          {[".gb", ".gbk", ".fasta", ".fa"].map((ext) => (
            <span key={ext} className="mono text-indigo-400 text-xs">{ext}{" "}</span>
          ))}
          · <span className="text-gray-400">multiple files supported</span>
        </p>
        <button
          type="button"
          className="text-xs bg-white/5 hover:bg-white/8 border border-white/10 px-4 py-2 rounded-lg transition-colors text-gray-300"
        >
          Browse files
        </button>
      </div>

      {/* Upload queue */}
      {queue.length > 0 && (
        <div className="bg-[#0f0f1e] border border-white/6 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/5">
            <p className="text-xs text-gray-400 font-medium">
              {queue.length} file{queue.length > 1 ? "s" : ""} queued
            </p>
            {!running && (
              <button onClick={clear} className="text-gray-600 hover:text-gray-400 transition-colors">
                <X size={13} />
              </button>
            )}
          </div>
          <div className="divide-y divide-white/5">
            {queue.map((entry) => (
              <div key={entry.file.name} className="flex items-center gap-3 px-4 py-2.5">
                {statusIcon(entry.status)}
                <span className="text-xs text-gray-300 flex-1 truncate">{entry.file.name}</span>
                <span className="text-[10px] text-gray-600 mono shrink-0">
                  {(entry.file.size / 1024).toFixed(0)} KB
                </span>
                {entry.status === "done" && entry.jobId && (
                  <a
                    href={`/jobs/${entry.jobId}`}
                    className="text-[10px] text-indigo-400 hover:text-indigo-300 shrink-0 transition-colors"
                  >
                    View →
                  </a>
                )}
                {entry.status === "error" && (
                  <span className="text-[10px] text-red-400 shrink-0">{entry.error}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
