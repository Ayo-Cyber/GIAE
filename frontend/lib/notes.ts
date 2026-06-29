"use client";

const KEY = "giae:notes";

type NoteStore = Record<string, string>; // `${jobId}:${geneId}` → note text

function load(): NoteStore {
  if (typeof window === "undefined") return {};
  try { return JSON.parse(localStorage.getItem(KEY) ?? "{}"); }
  catch { return {}; }
}

function save(store: NoteStore) {
  localStorage.setItem(KEY, JSON.stringify(store));
}

export function getNote(jobId: string, geneId: string): string {
  return load()[`${jobId}:${geneId}`] ?? "";
}

export function setNote(jobId: string, geneId: string, text: string): void {
  const store = load();
  if (text.trim()) {
    store[`${jobId}:${geneId}`] = text;
  } else {
    delete store[`${jobId}:${geneId}`];
  }
  save(store);
}

export function getAllNotes(): Array<{ jobId: string; geneId: string; text: string }> {
  return Object.entries(load()).map(([key, text]) => {
    const [jobId, ...rest] = key.split(":");
    return { jobId, geneId: rest.join(":"), text };
  });
}
