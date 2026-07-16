import { getToken } from "next-auth/jwt";
import { NextRequest } from "next/server";

// Paths that don't require a logged-in session
const PUBLIC_PREFIXES = ["auth/", "health", "waitlist", "share/"];

const API_URL = process.env.API_URL || "http://localhost:8000";

// Refresh the backend access token if it's within this window of expiry, so a
// proxied call never forwards a token that's about to (or already has) lapsed.
const REFRESH_SKEW_MS = 60_000;

async function refreshAccess(refreshToken: string): Promise<string | null> {
  try {
    const res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return null;
    return (await res.json()).access_token as string;
  } catch {
    return null;
  }
}

async function handler(
  req: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const path = params.path.join("/");
  const isPublic = PUBLIC_PREFIXES.some((p) => path.startsWith(p));

  let accessToken: string | undefined;
  if (!isPublic) {
    // Read the raw JWT (has accessToken, accessTokenExpires, refreshToken).
    // Refreshing here — not in the jwt callback — avoids the concurrent
    // cookie-rewrite race that dropped the refresh token.
    const token = await getToken({ req, secret: process.env.NEXTAUTH_SECRET });
    if (!token) {
      return Response.json({ error: "Unauthorized" }, { status: 401 });
    }
    accessToken = token.accessToken as string | undefined;
    const expires = (token.accessTokenExpires as number | undefined) ?? 0;
    const refreshTok = token.refreshToken as string | undefined;
    if ((!accessToken || Date.now() > expires - REFRESH_SKEW_MS) && refreshTok) {
      const fresh = await refreshAccess(refreshTok);
      if (fresh) accessToken = fresh;
    }
    if (!accessToken) {
      return Response.json({ error: "Session expired; sign in again." }, { status: 401 });
    }
  }

  const url = `${API_URL}/api/v1/${path}${req.nextUrl.search}`;
  const reqHeaders: Record<string, string> = {};
  if (accessToken) reqHeaders["authorization"] = `Bearer ${accessToken}`;

  const ALLOWED_EXTENSIONS = [".gb", ".gbk", ".fasta", ".fa", ".fna"];
  const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB

  let body: BodyInit | undefined;
  if (req.method !== "GET" && req.method !== "HEAD") {
    const contentType = req.headers.get("content-type") || "";
    if (contentType.includes("multipart/form-data")) {
      const form = await req.formData();
      // Validate genome file if this is a job creation request
      if (path === "jobs") {
        const file = form.get("file");
        if (!(file instanceof File)) {
          return Response.json({ error: "No file provided." }, { status: 400 });
        }
        const ext = "." + file.name.split(".").pop()?.toLowerCase();
        if (!ALLOWED_EXTENSIONS.includes(ext)) {
          return Response.json(
            { error: `Unsupported file type "${ext}". Allowed: ${ALLOWED_EXTENSIONS.join(", ")}` },
            { status: 400 }
          );
        }
        if (file.size > MAX_FILE_SIZE) {
          return Response.json(
            { error: `File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Maximum is 50 MB.` },
            { status: 413 }
          );
        }
      }
      body = form;
    } else {
      reqHeaders["content-type"] = contentType || "application/json";
      body = await req.text();
    }
  }

  const res = await fetch(url, { method: req.method, headers: reqHeaders, body });
  const text = await res.text();

  return new Response(text, {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") || "application/json" },
  });
}

export {
  handler as GET,
  handler as POST,
  handler as PUT,
  handler as DELETE,
  handler as PATCH,
};
