import { NextRequest, NextResponse } from "next/server";
import { proxyPost, getSessionCookieFromRequest } from "@/lib/api";

export async function POST(request: NextRequest) {
  const token = getSessionCookieFromRequest(request);
  try {
    const body = await request.json();
    const data = await proxyPost("/api/adherence/plans", body, token);
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Failed to start adherence plan" },
      { status: 400 }
    );
  }
}
