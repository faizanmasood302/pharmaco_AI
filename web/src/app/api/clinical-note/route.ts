import { NextRequest, NextResponse } from "next/server";
import { proxyPost } from "@/lib/api";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    console.log("Clinical note request received:", JSON.stringify(body, null, 2));

    const data = await proxyPost("/api/clinical-note", body);
    console.log("Clinical note response:", JSON.stringify(data, null, 2));

    // Ensure response has note field
    if (!data.note) {
      console.error("No note in response:", data);
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
