import { NextRequest, NextResponse } from "next/server";
import { proxyGet } from "@/lib/api";

export async function GET(request: NextRequest) {
  const token = request.cookies.get("better-auth.session_token")?.value;
  try {
    const data = await proxyGet("/api/medications", token);
    return NextResponse.json(data);
  } catch (e) {
    const message = e instanceof Error ? e.message : "Failed to load medications";
    // Check if it's an auth error to return 401 instead of 503
    const isAuthError = message.toLowerCase().includes("session") || 
                        message.toLowerCase().includes("log in") ||
                        message.toLowerCase().includes("auth") ||
                        message.toLowerCase().includes("unauthorized");
    
    return NextResponse.json(
      { error: message },
      { status: isAuthError ? 401 : 503 }
    );
  }
}
