import { NextRequest, NextResponse } from "next/server";
import { getAuth } from "@clerk/nextjs/server";

export async function middleware(request: NextRequest) {
  // In a production app with Clerk, you would check auth here
  // const { userId } = getAuth(request);
  // if (!userId) return NextResponse.redirect(new URL('/login', request.url));
  
  return NextResponse.next();
}

// Ensure middleware doesn't run on static assets
export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|public/).*)',
  ],
};
