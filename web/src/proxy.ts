import { NextRequest, NextResponse } from "next/server";

export async function proxy(request: NextRequest) {
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
  const sessionCookie = request.cookies.get("better-auth.session_token");

  if (!sessionCookie) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  // 3. Verify the session is still valid in the database
  // Catches stale cookies (e.g. session deleted server-side while cookie persists)
  try {
    const sessionCheck = await fetch(
      `${request.nextUrl.origin}/api/auth/get-session`,
      {
        headers: {
          cookie: request.headers.get("cookie") ?? "",
        },
      }
    );

    const body = await sessionCheck.json().catch(() => null);
    const isValid = sessionCheck.ok && body?.session;

    if (!isValid) {
      // Clear the stale cookie and redirect to login
      const response = NextResponse.redirect(new URL("/login", request.url));
      response.cookies.delete("better-auth.session_token");
      return response;
    }
  } catch {
    // If session check itself fails (e.g. server cold start), fail open
    // and let the API route handle auth — avoids redirect loop on startup
    console.warn("Session verification fetch failed, failing open");
  }

  return NextResponse.next();
}

// Ensure middleware doesn't run on static assets
export const config = {
  matcher: [
    '/((?!_next/static|_next/image|public/).*)',
  ],
};