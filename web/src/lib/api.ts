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

let cachedToken: string | null = null;
let tokenExpiresAt: number = 0;

export async function getAuthToken(): Promise<string | null> {
  if (cachedToken && Date.now() < tokenExpiresAt - 60000) {
    return cachedToken;
  }

  try {
    const res = await fetch(`${AGENT_SERVER}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        email: process.env.DEMO_EMAIL || "doctor@clinic.com", 
        password: process.env.DEMO_PASSWORD || "testpass" 
      }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    cachedToken = data.access_token;
    tokenExpiresAt = Date.now() + 3600 * 1000;
    return cachedToken;
  } catch (e) {
    console.error("Auth error:", e);
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
