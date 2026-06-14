import { NextRequest, NextResponse } from "next/server";
import { proxyPost, getSessionCookieFromRequest } from "@/lib/api";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ checkInId: string }> }
) {
  const token = getSessionCookieFromRequest(request);
  const { checkInId } = await params;
  try {
    const body = await request.json();
    const data = await proxyPost(`/api/adherence/check-ins/${checkInId}`, body, token);
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Check-in failed" },
      { status: 400 }
    );
  }
}
