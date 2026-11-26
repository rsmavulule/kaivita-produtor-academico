import { CONNECTION_MESSAGE, parseApiError, type ParsedApiError } from "./errors";

const REQUEST_TIMEOUT_MS = 8_000;

/**
 * Lê API_URL em cada pedido. A chave é composta para o compilador do Next.js
 * não gravar o valor no bundle durante o build: no Compose o endereço só
 * existe quando o contentor arranca.
 */
function readApiUrl(): string | null {
  const name = ["API", "URL"].join("_");
  const value = process.env[name];
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (trimmed === "") return null;
  return trimmed.replace(/\/$/, "");
}

type ApiCall =
  | { kind: "ok"; status: number; data: unknown }
  | ParsedApiError;

export async function apiRequest(
  path: string,
  init?: { method?: string; token?: string; body?: unknown },
): Promise<ApiCall> {
  const apiUrl = readApiUrl();
  if (apiUrl === null) {
    return { kind: "unavailable", status: 0, message: CONNECTION_MESSAGE };
  }

  const headers = new Headers({ accept: "application/json" });
  if (init?.body !== undefined) headers.set("content-type", "application/json");
  if (init?.token) headers.set("authorization", `Bearer ${init.token}`);

  try {
    const response = await fetch(`${apiUrl}${path}`, {
      method: init?.method ?? "GET",
      headers,
      body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
      cache: "no-store",
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
    const data = await readBody(response);
    if (response.ok) return { kind: "ok", status: response.status, data };
    return parseApiError(response.status, data);
  } catch {
    return { kind: "unavailable", status: 0, message: CONNECTION_MESSAGE };
  }
}

async function readBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (text === "") return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

export type LoginResult =
  | { kind: "ready"; token: string; expiresIn: number }
  | ParsedApiError;

export async function requestLogin(email: string, password: string): Promise<LoginResult> {
  const result = await apiRequest("/auth/login", {
    method: "POST",
    body: { email, password },
  });
  if (result.kind !== "ok") return result;
  if (!isLoginPayload(result.data)) {
    return { kind: "unavailable", status: 200, message: CONNECTION_MESSAGE };
  }
  return {
    kind: "ready",
    token: result.data.access_token,
    expiresIn: result.data.expires_in,
  };
}

export type MeResult =
  | { kind: "ready"; email: string }
  | { kind: "invalid" }
  | { kind: "unavailable" };

export async function requestMe(token: string): Promise<MeResult> {
  const result = await apiRequest("/auth/me", { token });
  if (result.kind === "ok") {
    if (!isMePayload(result.data)) return { kind: "unavailable" };
    return { kind: "ready", email: result.data.email };
  }
  if (result.kind === "unauthorized") return { kind: "invalid" };
  return { kind: "unavailable" };
}

function isLoginPayload(
  data: unknown,
): data is { access_token: string; token_type: "bearer"; expires_in: number } {
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    typeof record.access_token === "string" &&
    record.access_token.length > 0 &&
    record.token_type === "bearer" &&
    typeof record.expires_in === "number" &&
    Number.isInteger(record.expires_in) &&
    record.expires_in >= 60 &&
    record.expires_in <= 86_400
  );
}

function isMePayload(data: unknown): data is { email: string; status: string } {
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    typeof record.email === "string" &&
    record.email.includes("@") &&
    record.status === "active"
  );
}
