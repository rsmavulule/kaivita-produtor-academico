import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

export const manifestPath = path.join(process.cwd(), "e2e", ".run-manifest.json");

const TEST_EMAIL = /^i(?:5\d+|73)-[\w.-]+@example\.com$/;

export function resetManifest(): void {
  mkdirSync(path.dirname(manifestPath), { recursive: true });
  writeFileSync(manifestPath, JSON.stringify({ emails: [] }), "utf8");
}

export function rememberAccount(email: string): void {
  const normalized = email.trim().toLowerCase();
  if (!TEST_EMAIL.test(normalized)) {
    throw new Error("A conta de teste tem de usar o domínio example.com e o prefixo i5.");
  }
  const emails = manifestEmails();
  if (!emails.includes(normalized)) emails.push(normalized);
  writeFileSync(manifestPath, JSON.stringify({ emails }), "utf8");
}

export function manifestEmails(): string[] {
  if (!existsSync(manifestPath)) return [];
  try {
    const parsed = JSON.parse(readFileSync(manifestPath, "utf8")) as { emails?: unknown };
    if (!Array.isArray(parsed.emails)) return [];
    return parsed.emails.filter((email): email is string => typeof email === "string" && TEST_EMAIL.test(email));
  } catch {
    return [];
  }
}
