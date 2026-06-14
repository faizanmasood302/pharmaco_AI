import { NextRequest, NextResponse } from "next/server";

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (
    pathname.startsWith("/api/auth") ||
    pathname.startsWith("/login") ||
    pathname.startsWith("/signup") ||
    pathname === "/favicon.ico"
  ) {
    return NextResponse.next();
  }

  const SESSION_COOKIE = "better-auth.session_token";
  const SECURE_SESSION_COOKIE = "__Secure-better-auth.session_token";
  const LEGACY_SECURE_COOKIE = "_Secure-better-auth.session_token";

  const sessionCookie =
    request.cookies.get(SECURE_SESSION_COOKIE) ||
    request.cookies.get(SESSION_COOKIE) ||
    request.cookies.get(LEGACY_SECURE_COOKIE);

  if (!sessionCookie) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

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
      const response = NextResponse.redirect(new URL("/login", request.url));
      response.cookies.delete(SESSION_COOKIE);
      response.cookies.delete(SECURE_SESSION_COOKIE);
      response.cookies.delete(LEGACY_SECURE_COOKIE);
      return response;
    }
  } catch {
    if (process.env.NODE_ENV === "development") {
      console.warn("Session verification fetch failed in development; continuing locally");
      return NextResponse.next();
    }

    const response = NextResponse.redirect(new URL("/login", request.url));
    response.cookies.delete(SESSION_COOKIE);
    response.cookies.delete(SECURE_SESSION_COOKIE);
    response.cookies.delete(LEGACY_SECURE_COOKIE);
    return response;
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|public/).*)"],
};
