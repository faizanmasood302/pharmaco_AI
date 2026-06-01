import { NextRequest, NextResponse } from "next/server";
import { proxyPost } from "@/lib/api";

export async function POST(request: NextRequest) {
  const token = request.cookies.get("better-auth.session_token")?.value;
  const body = await request.json();

  try {
    const data = await proxyPost("/api/generate-therapy", body, token);
    return NextResponse.json(data);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Therapy generation failed";
    const lower = message.toLowerCase();
    const status =
      lower.includes("session") ||
      lower.includes("auth") ||
      lower.includes("unauthorized")
        ? 401
        : lower.includes("unreachable") || lower.includes("fetch failed")
          ? 503
          : 400;

    return NextResponse.json({ error: message }, { status });
  }
}
