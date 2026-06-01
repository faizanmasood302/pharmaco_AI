import { NextRequest, NextResponse } from "next/server";
import { proxyGet } from "@/lib/api";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ patientId: string }> }
) {
  const { patientId } = await params;
  try {
    const data = await proxyGet(`/api/patients/${patientId}/reports`);
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Failed to fetch patient reports" },
      { status: 400 }
    );
  }
}
