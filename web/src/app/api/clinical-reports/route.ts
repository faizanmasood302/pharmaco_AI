import { NextRequest, NextResponse } from "next/server";
import { proxyPost, getSessionCookieFromRequest } from "@/lib/api";

export async function POST(request: NextRequest) {
  const token = getSessionCookieFromRequest(request);
  const body = await request.json();

  try {
    const data = await proxyPost("/api/clinical-reports", body, token);
    return NextResponse.json(data);
  } catch (e) {
    const message = e instanceof Error ? e.message : "Clinical report save failed";
    const lower = message.toLowerCase();
    const status =
      lower.includes("session") ||
      lower.includes("log in") ||
      lower.includes("auth") ||
      lower.includes("unauthorized")
        ? 401
        : 400;

    return NextResponse.json({ error: message }, { status });
  }
}
