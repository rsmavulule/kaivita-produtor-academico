import { existsSync, mkdirSync, readFileSync } from "node:fs";
import path from "node:path";

import { credentialsPath } from "./global-setup";

export type Credentials = { email: string; password: string };

export function credentials(): Credentials {
  const raw = readFileSync(credentialsPath, "utf8");
  const parsed = JSON.parse(raw) as Credentials;
  if (!parsed.email || !parsed.password) {
    throw new Error("Credenciais de teste em falta.");
  }
  return parsed;
}

export const appOrigin = process.env.E2E_BASE_URL ?? "http://127.0.0.1:3100";

export function hostApiUrl(): string {
  if (process.env.API_URL) return process.env.API_URL.replace(/\/$/, "");
  const port = envValue("API_PORT");
  if (port && /^\d+$/.test(port)) return `http://127.0.0.1:${port}`;
  return "http://127.0.0.1:8010";
}

export function hostWebUrl(): string {
  if (process.env.E2E_BASE_URL) return process.env.E2E_BASE_URL.replace(/\/$/, "");
  const port = envValue("WEB_PORT");
  if (port && /^\d+$/.test(port)) return `http://127.0.0.1:${port}`;
  return "http://127.0.0.1:3010";
}

export function tokenLifetimeSeconds(): number {
  const raw = envValue("JWT_EXPIRES_IN");
  const parsed = raw ? Number(raw) : 1800;
  return Number.isInteger(parsed) ? parsed : 1800;
}

export function shot(name: string): string {
  return evidenceShot("I5.1", name);
}

/** A regressão grava capturas temporárias. E2E_EVIDENCE=I5.5 grava só esse incremento. */
export function evidenceShot(increment: string, name: string): string {
  const permanent = process.env.E2E_EVIDENCE === increment;
  const dir = permanent
    ? path.resolve(process.cwd(), "..", "docs", "evidencias", increment, "capturas")
    : path.resolve(process.cwd(), "test-results", "capturas");
  mkdirSync(dir, { recursive: true });
  return path.join(dir, name);
}

function envValue(key: string): string | undefined {
  const envPath = path.resolve(process.cwd(), "..", ".env");
  if (!existsSync(envPath)) return undefined;
  for (const line of readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const separator = trimmed.indexOf("=");
    if (separator === -1) continue;
    if (trimmed.slice(0, separator).trim() !== key) continue;
    return trimmed.slice(separator + 1).trim();
  }
  return undefined;
}
