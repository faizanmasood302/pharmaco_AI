import { NextRequest, NextResponse } from "next/server";
import { proxyPost, getSessionCookieFromRequest } from "@/lib/api";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const token = getSessionCookieFromRequest(request);
  const body = await request.json();
  const { id } = await params;

  try {
    const data = await proxyPost(`/api/therapy-requests/${id}/decision`, body, token);
    return NextResponse.json(data);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Decision update failed";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
