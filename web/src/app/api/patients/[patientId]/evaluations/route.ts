import { NextRequest, NextResponse } from "next/server";
import { proxyGet, getSessionCookieFromRequest } from "@/lib/api";

export async function GET(
  request: NextRequest,
  { params }: { params: { patientId: string } }
) {
  const token = getSessionCookieFromRequest(request);
  const { patientId } = await params;
  try {
    const data = await proxyGet(`/api/evaluations/${patientId}`, token);
    return NextResponse.json(data);
  } catch (e) {
    const message = e instanceof Error ? e.message : "Failed to load history";
    const isAuthError =
      message.toLowerCase().includes("session") ||
      message.toLowerCase().includes("log in") ||
      message.toLowerCase().includes("auth") ||
      message.toLowerCase().includes("unauthorized");

    return NextResponse.json(
      { error: message },
      { status: isAuthError ? 401 : 503 }
    );
  }
}
