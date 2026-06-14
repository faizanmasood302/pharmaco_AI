// evaluation 
import { NextRequest, NextResponse } from "next/server";
import { proxyPost, getSessionCookieFromRequest } from "@/lib/api";

export async function POST(request: NextRequest) {
  const token = getSessionCookieFromRequest(request);
  const body = await request.json();

  try {
    const data = await proxyPost('/api/evaluate-prescription', body, token);
    return NextResponse.json(data);
  } catch (error: unknown) {
    console.error("Evaluation API error:", error);
    const errMsg = error instanceof Error ? error.message : String(error);
    
    // Check if it's an auth error to return 401 instead of 503/400
    const isAuthError = errMsg.toLowerCase().includes("session") || 
                        errMsg.toLowerCase().includes("log in") ||
                        errMsg.toLowerCase().includes("auth") ||
                        errMsg.toLowerCase().includes("unauthorized");

    const status = isAuthError ? 401 : 
                  (errMsg.includes("unreachable") || errMsg.includes("fetch failed") ? 503 : 400);
    
    return NextResponse.json(
      { error: errMsg },
      { status }
    );
  }
}
