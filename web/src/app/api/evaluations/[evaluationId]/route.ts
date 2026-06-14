import { NextRequest, NextResponse } from "next/server";
import { proxyGet, getSessionCookieFromRequest } from "@/lib/api";

export async function GET(
  request: NextRequest,
  { params }: { params: { evaluationId: string } }
) {
  const token = getSessionCookieFromRequest(request);
  const { evaluationId } = await params;

  try {
    const data = await proxyGet(`/api/evaluations/${evaluationId}`, token);
    return NextResponse.json(data);
  } catch (e) {
    const message = e instanceof Error ? e.message : "Failed to load evaluations";
    const lower = message.toLowerCase();
    const status =
      lower.includes("session") ||
      lower.includes("log in") ||
      lower.includes("auth") ||
      lower.includes("unauthorized")
        ? 401
        : lower.includes("unreachable") || lower.includes("fetch failed")
          ? 503
          : 400;

    return NextResponse.json({ error: message }, { status });
  }
}
