// evaluation 
import { NextRequest, NextResponse } from "next/server";
import { proxyPost, getSessionCookieFromRequest } from "@/lib/api";

// Evaluation endpoint — uses a longer timeout to handle DB cold starts and 5-agent pipeline
const EVALUATE_TIMEOUT = 60_000; // 60 seconds

export async function POST(request: NextRequest) {
  const token = getSessionCookieFromRequest(request);
  const body = await request.json();

  try {
    const data = await proxyPost('/api/evaluate-prescription', body, token, EVALUATE_TIMEOUT);
    return NextResponse.json(data);
  } catch (error: unknown) {
    console.error("Evaluation API error:", error);
    const errMsg = error instanceof Error ? error.message : String(error);
    
    const isAuthError = errMsg.toLowerCase().includes("session") || 
                        errMsg.toLowerCase().includes("log in") ||
                        errMsg.toLowerCase().includes("auth") ||
                        errMsg.toLowerCase().includes("unauthorized");

    const isTimeout = errMsg.includes("Gateway Timeout") ||
                      errMsg.includes("aborted") ||
                      errMsg.includes("timed out");

    const status = isAuthError ? 401 : 
                  isTimeout   ? 504 :
                  errMsg.includes("unreachable") || errMsg.includes("fetch failed") ? 503 : 400;
    
    return NextResponse.json(
      { error: errMsg },
      { status }
    );
  }
}
