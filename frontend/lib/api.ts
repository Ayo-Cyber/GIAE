import type { Job, GeneRow, CreateJobResponse, DarkGene, ApiKey, CreatedApiKey, Notification, WatchlistEntry } from "./types";

// Retry with exponential backoff for transient errors (5xx, network failures).
// 4xx errors are not retried — they indicate a client mistake.
async function request<T>(
  path: string,
  init?: RequestInit,
  retries = 3,
  backoffMs = 300,
): Promise<T> {
  let lastError: Error = new Error("Unknown error");

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(path, {
        headers: { "Content-Type": "application/json", ...init?.headers },
        ...init,
      });

      if (res.status === 401) {
        if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
          window.location.href = "/login?expired=1";
        }
        throw new Error("Session expired");
      }

      // Don't retry client errors
      if (res.status >= 400 && res.status < 500) {
        throw new Error(`API error ${res.status}: ${await res.text()}`);
      }

      if (!res.ok) {
        // 5xx — retry
        lastError = new Error(`API error ${res.status}`);
        if (attempt < retries) {
          await new Promise((r) => setTimeout(r, backoffMs * 2 ** attempt));
          continue;
        }
        throw lastError;
      }

      return res.json();
    } catch (err) {
      if (err instanceof Error && err.message === "Session expired") throw err;
      // Network-level failures (fetch throws) — retry
      lastError = err instanceof Error ? err : new Error(String(err));
      if (attempt < retries) {
        await new Promise((r) => setTimeout(r, backoffMs * 2 ** attempt));
        continue;
      }
    }
  }

  throw lastError;
}

export const api = {
  health: () => request<{ status: string }>("/api/v1/health"),

  createJob: async (file: File): Promise<CreateJobResponse> => {
    const form = new FormData();
    form.append("file", file);
    const r = await fetch("/api/v1/jobs", { method: "POST", body: form });
    return r.json();
  },

  listJobs: () =>
    request<{ jobs: Omit<Job, "genes">[] }>("/api/v1/jobs").then((r) => r.jobs),

  getJob: (jobId: string) => request<Job>(`/api/v1/jobs/${jobId}`),

  rerunJob: (jobId: string) =>
    request<{ job_id: string; status: string }>(`/api/v1/jobs/${jobId}/rerun`, { method: "POST" }),

  cancelJob: (jobId: string) =>
    request<{ job_id: string; status: string }>(`/api/v1/jobs/${jobId}/cancel`, { method: "POST" }),

  workerStatus: () =>
    request<{ online: boolean; workers: string[]; active_tasks: number; queued_tasks: number; checked_at: string }>("/api/v1/worker/status"),

  listDarkGenes: () =>
    request<{ total: number; genes: DarkGene[] }>("/api/v1/dark-genes").then((r) => r.genes),

  listApiKeys: () =>
    request<{ keys: ApiKey[] }>("/api/v1/keys").then((r) => r.keys),

  createApiKey: (name: string, expiresInDays?: number) =>
    request<CreatedApiKey>("/api/v1/keys", {
      method: "POST",
      body: JSON.stringify({ name, expires_in_days: expiresInDays ?? null }),
    }),

  revokeApiKey: (keyId: string) =>
    request<void>(`/api/v1/keys/${keyId}`, { method: "DELETE" }),

  shareJob: (jobId: string) =>
    request<{ token: string; url: string }>(`/api/v1/jobs/${jobId}/share`, { method: "POST" }),

  getSharedJob: (token: string) =>
    request<Job>(`/api/v1/share/${token}`),

  getNotifications: () =>
    request<{ notifications: Notification[] }>("/api/v1/notifications").then((r) => r.notifications),

  getJobHistory: (jobId: string) =>
    request<{ previous_genes: GeneRow[]; current_genes: GeneRow[] }>(`/api/v1/jobs/${jobId}/history`),

  getWatchlist: () =>
    request<{ entries: WatchlistEntry[] }>("/api/v1/watchlist").then((r) => r.entries),

  addToWatchlist: (locus: string, gene_name: string) =>
    request<{ id: string; locus: string; status: string }>("/api/v1/watchlist", {
      method: "POST",
      body: JSON.stringify({ locus, gene_name }),
    }),

  removeFromWatchlist: (locus: string) =>
    request<void>(`/api/v1/watchlist/${encodeURIComponent(locus)}`, { method: "DELETE" }),

  joinWaitlist: (email: string) =>
    request<{ status: string }>("/api/v1/waitlist", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  pollJob: (
    jobId: string,
    onUpdate: (job: Job) => void,
    intervalMs = 3000
  ): (() => void) => {
    const id = setInterval(async () => {
      try {
        const job = await api.getJob(jobId);
        onUpdate(job);
        if (job.status === "COMPLETED" || job.status === "FAILED") {
          clearInterval(id);
        }
      } catch {
        // keep polling on transient errors
      }
    }, intervalMs);
    return () => clearInterval(id);
  },
};
