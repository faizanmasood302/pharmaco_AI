import { NextRequest, NextResponse } from "next/server";
import { proxyPost } from "@/lib/api";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ evaluationId: string }> }
) {
  const token = request.cookies.get("better-auth.session_token")?.value;
  const { evaluationId } = await params;
  try {
    const body = await request.json();
    const data = await proxyPost(`/api/evaluations/${evaluationId}/decision`, body, token);
    return NextResponse.json(data);
  } catch (e) {
    const message = e instanceof Error ? e.message : "Failed to update evaluation decision";
    const isAuthError =
      message.toLowerCase().includes("session") ||
      message.toLowerCase().includes("log in") ||
      message.toLowerCase().includes("auth") ||
      message.toLowerCase().includes("unauthorized");

    return NextResponse.json(
      { error: message },
      { status: isAuthError ? 401 : 400 }
    );
  }
}
