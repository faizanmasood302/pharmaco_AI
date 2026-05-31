import { NextRequest, NextResponse } from "next/server";
import { proxyPost } from "@/lib/api";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const data = await proxyPost("/api/ingest-fhir", { bundle: body.bundle ?? body });
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "FHIR ingest failed" },
      { status: 400 }
    );
  }
}
