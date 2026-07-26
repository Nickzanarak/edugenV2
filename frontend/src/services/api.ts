import { hasDetail } from "../utils/helpers";

export type AuthHeaders = Record<string, string>;

export function getAPIBase(): string {
  const env = process.env.NEXT_PUBLIC_API;
  const fallback = "http://localhost:8000";
  const base = env && env.trim() ? env.trim() : fallback;
  return base.replace(/\/+$/, "");
}

export function isDemoAuthEnabled(): boolean {
  return process.env.NEXT_PUBLIC_ALLOW_DEMO_AUTH === "true";
}

export function canUseProtectedApi(hasUser: boolean): boolean {
  return hasUser || isDemoAuthEnabled();
}

export function buildAuthHeaders(token: string | null, demoUid = "demo-user"): AuthHeaders {
  if (token) return { Authorization: `Bearer ${token}` };
  if (isDemoAuthEnabled()) return { "X-User-Id": demoUid.trim() || "demo-user" };
  return {};
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function extractErrorMessage(body: unknown, fallback: string): string {
  if (hasDetail(body) && typeof body.detail === "string") return body.detail;
  if (typeof body === "string" && body.trim()) return body;
  return fallback;
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit & { auth?: AuthHeaders; json?: unknown } = {},
): Promise<T> {
  const { auth, json, headers: optHeaders, ...rest } = options;
  const headers: Record<string, string> = {
    ...(optHeaders as Record<string, string> | undefined),
  };
  if (auth) Object.assign(headers, auth);
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    rest.body = JSON.stringify(json);
  }

  const res = await fetch(`${getAPIBase()}${path}`, { ...rest, headers });
  const contentType = res.headers.get("content-type") || "";

  if (!res.ok) {
    const body = contentType.includes("application/json")
      ? await res.json().catch(() => null)
      : await res.text().catch(() => "");
    throw new ApiError(res.status, extractErrorMessage(body, res.statusText || `HTTP ${res.status}`));
  }

  if (contentType.includes("application/json")) {
    return res.json() as Promise<T>;
  }
  return res as unknown as T;
}

export async function apiFetchBlob(
  path: string,
  options: RequestInit & { auth?: AuthHeaders; json?: unknown } = {},
): Promise<Response> {
  const { auth, json, headers: optHeaders, ...rest } = options;
  const headers: Record<string, string> = {
    ...(optHeaders as Record<string, string> | undefined),
  };
  if (auth) Object.assign(headers, auth);
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    rest.body = JSON.stringify(json);
  }

  const res = await fetch(`${getAPIBase()}${path}`, { ...rest, headers });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body || res.statusText || `HTTP ${res.status}`);
  }
  return res;
}
