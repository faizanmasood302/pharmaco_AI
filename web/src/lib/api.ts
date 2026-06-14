import { authClient } from "./auth-client";

const AGENT_SERVER =
  process.env.AGENT_SERVER_URL ?? "http://127.0.0.1:8000";

const FETCH_TIMEOUT = 15000; // 15 seconds

async function fetchWithTimeout(url: string, options: RequestInit & { timeout?: number } = {}) {
  const { timeout = FETCH_TIMEOUT, ...fetchOptions } = options;
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(url, {
      ...fetchOptions,
      signal: controller.signal
    });
    return response;
  } finally {
    clearTimeout(id);
  }
}

const SESSION_COOKIE_VARIANTS = [
  "better-auth.session_token",
  "__Secure-better-auth.session_token",
  "_Secure-better-auth.session_token",
];

export function getSessionCookieFromRequest(request: { cookies: { get: (name: string) => { value?: string } | undefined } }): string | undefined {
  for (const name of SESSION_COOKIE_VARIANTS) {
    const cookie = request.cookies.get(name);
    if (cookie?.value) return cookie.value;
  }
  return undefined;
}

export async function getAuthToken(): Promise<string | null> {
  if (typeof window !== "undefined") {
    const { data } = await authClient.getSession();
    return data?.session?.token ?? null;
  } else {
    const { cookies } = await import("next/headers");
    const cookieStore = await cookies();
    for (const name of SESSION_COOKIE_VARIANTS) {
      const cookie = cookieStore.get(name);
      if (cookie?.value) return cookie.value;
    }
    return null;
  }
}

async function handleApiError(response: Response) {
  try {
    const data = await response.json();
    return data.error?.message || data.detail || `Request failed with status ${response.status}`;
  } catch {
    return `HTTP ${response.status}: ${response.statusText}`;
  }
}

export async function proxyGet(path: string, explicitToken?: string) {
  const token = explicitToken ?? await getAuthToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetchWithTimeout(`${AGENT_SERVER}${path}`, { 
    headers,
    cache: "no-store" 
  }).catch(err => {
    console.error(`Fetch error for ${path}:`, err);
    throw new Error(`Agent Server unreachable at ${AGENT_SERVER}${path}: ${err.message}`);
  });
  
  if (!res.ok) {
    const errorMsg = await handleApiError(res);
    throw new Error(errorMsg);
  }

  const text = await res.text();
  return text ? JSON.parse(text) : {};
}

export async function proxyPost(path: string, body: unknown, explicitToken?: string) {
  const token = explicitToken ?? await getAuthToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetchWithTimeout(`${AGENT_SERVER}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  
  if (!res.ok) {
    const errorMsg = await handleApiError(res);
    throw new Error(errorMsg);
  }

  const text = await res.text();
  return text ? JSON.parse(text) : {};
}
