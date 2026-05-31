import { NextRequest, NextResponse } from "next/server";
import { proxyGet } from "@/lib/api";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ patientId: string }> }
) {
  const { patientId } = await params;
  try {
    const data = await proxyGet(`/api/evaluations/${patientId}`);
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Failed to load history" },
      { status: 503 }
    );
  }
}
