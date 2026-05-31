import { NextRequest, NextResponse } from "next/server";

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 1. Allow auth-related paths and static assets
  if (
    pathname.startsWith("/api/auth") ||
    pathname.startsWith("/login") ||
    pathname.startsWith("/signup") ||
    pathname === "/favicon.ico"
  ) {
    return NextResponse.next();
  }

  // 2. Check for BetterAuth session cookie
  // BetterAuth uses 'better-auth.session_token' by default
  const sessionCookie = request.cookies.get("better-auth.session_token");

  if (!sessionCookie) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  // 3. Optional: Verify session with the BetterAuth API
  // For maximum security, we'd verify the token here, but a cookie check 
  // is a good first line of defense for the UI.
  
  return NextResponse.next();
}

// Ensure middleware doesn't run on static assets
export const config = {
  matcher: [
    '/((?!_next/static|_next/image|public/).*)',
  ],
};
