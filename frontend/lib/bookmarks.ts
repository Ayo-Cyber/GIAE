"use client";

export interface Bookmark {
  geneId: string;
  geneName: string;
  locus: string;
  function: string | null;
  confidence: string | null;
  score: number | null;
  is_dark: boolean;
  jobId: string;
  jobFilename: string;
  savedAt: string; // ISO
}

const KEY = "giae:bookmarks";

export function getBookmarks(): Bookmark[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "[]");
  } catch {
    return [];
  }
}

export function isBookmarked(geneId: string): boolean {
  return getBookmarks().some((b) => b.geneId === geneId);
}

export function addBookmark(b: Omit<Bookmark, "savedAt">): void {
  const all = getBookmarks().filter((x) => x.geneId !== b.geneId);
  all.unshift({ ...b, savedAt: new Date().toISOString() });
  localStorage.setItem(KEY, JSON.stringify(all));
}

export function removeBookmark(geneId: string): void {
  const all = getBookmarks().filter((b) => b.geneId !== geneId);
  localStorage.setItem(KEY, JSON.stringify(all));
}

export function toggleBookmark(b: Omit<Bookmark, "savedAt">): boolean {
  if (isBookmarked(b.geneId)) {
    removeBookmark(b.geneId);
    return false;
  }
  addBookmark(b);
  return true;
}
