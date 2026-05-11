"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useRouter } from "next/navigation";
import { Upload, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

export function UploadZone() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(
    async (files: File[]) => {
      const file = files[0];
      if (!file) return;

      setLoading(true);
      setError(null);

      try {
        const { job_id } = await api.createJob(file);
        router.push(`/jobs/${job_id}`);
      } catch (e) {
        setError("Upload failed. Check the API is running.");
        setLoading(false);
      }
    },
    [router]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "chemical/x-genbank": [".gb", ".gbk"],
      "text/plain": [".fasta", ".fa", ".fna"],
      "application/octet-stream": [".gb", ".gbk", ".fasta", ".fa"],
    },
    maxFiles: 1,
    disabled: loading,
  });

  return (
    <div
      {...getRootProps()}
      className={cn(
        "border border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all",
        isDragActive
          ? "border-indigo-500/70 bg-indigo-500/5"
          : "border-white/10 hover:border-indigo-500/40 hover:bg-indigo-500/3",
        loading && "pointer-events-none opacity-60"
      )}
    >
      <input {...getInputProps()} />

      <div
        className={cn(
          "w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4 transition-colors",
          isDragActive
            ? "bg-indigo-600/30 border border-indigo-500/50"
            : "bg-indigo-600/15 border border-indigo-500/25"
        )}
      >
        {loading ? (
          <Loader2 size={22} className="text-indigo-400 animate-spin" />
        ) : (
          <Upload size={22} className="text-indigo-400" />
        )}
      </div>

      {loading ? (
        <>
          <p className="text-white font-medium mb-1">Uploading...</p>
          <p className="text-gray-500 text-sm">Starting interpretation job</p>
        </>
      ) : (
        <>
          <p className="text-white font-medium mb-1">
            {isDragActive ? "Drop it here" : "Drop your genome file here"}
          </p>
          <p className="text-gray-500 text-sm mb-4">
            Supports{" "}
            <span className="mono text-indigo-400 text-xs">.gb</span>{" · "}
            <span className="mono text-indigo-400 text-xs">.gbk</span>{" · "}
            <span className="mono text-indigo-400 text-xs">.fasta</span>{" · "}
            <span className="mono text-indigo-400 text-xs">.fa</span>
          </p>
          <button
            type="button"
            className="text-xs bg-white/5 hover:bg-white/8 border border-white/10 px-4 py-2 rounded-lg transition-colors text-gray-300"
          >
            Browse files
          </button>
        </>
      )}

      {error && (
        <p className="mt-4 text-xs text-red-400 bg-red-500/10 border border-red-500/20 px-3 py-2 rounded-lg">
          {error}
        </p>
      )}
    </div>
  );
}
