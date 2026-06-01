import { NextRequest, NextResponse } from "next/server";
import { proxyPost } from "@/lib/api";

export async function POST(request: NextRequest) {
  const token = request.cookies.get("better-auth.session_token")?.value;
  try {
    const body = await request.json();

    const data = await proxyPost("/api/clinical-note", body, token);

    // Ensure response has note field
    if (!data.note) {
      throw new Error("Backend response missing note field");
    }

    return NextResponse.json(data);
  } catch (e) {
    console.error("Clinical note API error:", e);
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Clinical note generation failed" },
      { status: 400 }
    );
  }
}
