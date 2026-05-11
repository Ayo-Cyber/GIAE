import { getServerSession } from "next-auth";
import { authOptions } from "../../auth/[...nextauth]/route";
import { NextRequest } from "next/server";

// Paths that don't require a logged-in session
const PUBLIC_PREFIXES = ["auth/", "health", "waitlist"];

const API_URL = process.env.API_URL || "http://localhost:8000";

async function handler(
  req: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const path = params.path.join("/");
  const isPublic = PUBLIC_PREFIXES.some((p) => path.startsWith(p));

  let accessToken: string | undefined;
  if (!isPublic) {
    const session = await getServerSession(authOptions);
    if (!session?.user) {
      return Response.json({ error: "Unauthorized" }, { status: 401 });
    }
    accessToken = (session as { accessToken?: string }).accessToken;
    if (!accessToken) {
      return Response.json({ error: "Session has no access token; sign in again." }, { status: 401 });
    }
  }

  const url = `${API_URL}/api/v1/${path}${req.nextUrl.search}`;
  const reqHeaders: Record<string, string> = {};
  if (accessToken) reqHeaders["authorization"] = `Bearer ${accessToken}`;

  let body: BodyInit | undefined;
  if (req.method !== "GET" && req.method !== "HEAD") {
    const contentType = req.headers.get("content-type") || "";
    if (contentType.includes("multipart/form-data")) {
      body = await req.formData();
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
