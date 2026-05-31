import { NextResponse } from "next/server";
import { proxyGet } from "@/lib/api";

export async function GET() {
  try {
    const data = await proxyGet("/api/medications");
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Failed to load medications" },
      { status: 503 }
    );
  }
}
