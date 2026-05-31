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

export async function getAuthToken(): Promise<string | null> {
  // BetterAuth stores session token in 'better-auth.session_token' cookie
  if (typeof window !== "undefined") {
    // Client-side: Read from cookie
    const cookies = document.cookie.split(";");
    const sessionCookie = cookies.find(c => c.trim().startsWith("better-auth.session_token="));
    return sessionCookie ? sessionCookie.split("=")[1] : null;
  } else {
    // Server-side: Read from Next.js headers
    const { cookies } = await import("next/headers");
    const cookieStore = await cookies();
    return cookieStore.get("better-auth.session_token")?.value || null;
  }
}

async function handleApiError(response: Response) {
...
  try {
    const data = await response.json();
    return data.error?.message || data.detail || `Request failed with status ${response.status}`;
  } catch {
    return `HTTP ${response.status}: ${response.statusText}`;
  }
}

export async function proxyGet(path: string) {
  const token = await getAuthToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetchWithTimeout(`${AGENT_SERVER}${path}`, { 
    headers,
    cache: "no-store" 
  });
  
  if (!res.ok) {
    const errorMsg = await handleApiError(res);
    throw new Error(errorMsg);
  }

  const text = await res.text();
  return text ? JSON.parse(text) : {};
}

export async function proxyPost(path: string, body: unknown) {
  const token = await getAuthToken();
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
