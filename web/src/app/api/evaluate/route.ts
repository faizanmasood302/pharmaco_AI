import { NextRequest, NextResponse } from "next/server";
import { proxyPost } from "@/lib/api";

export async function POST(request: NextRequest) {
  const body = await request.json();

  try {
    const data = await proxyPost('/api/evaluate-prescription', body);
    return NextResponse.json(data);
  } catch (error: any) {
    const errMsg = error?.message || String(error);
    const status = errMsg.includes("unreachable") || errMsg.includes("fetch failed") ? 503 : 400;
    
    return NextResponse.json(
      { error: errMsg },
      { status }
    );
  }
}
