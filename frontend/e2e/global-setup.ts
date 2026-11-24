import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

export const credentialsPath = path.join(process.cwd(), "e2e", ".credentials.json");

export default function globalSetup() {
  const email = `i51-${Date.now()}@example.com`;
  const password = randomBytes(18).toString("base64url");
  const backend = path.resolve(process.cwd(), "..", "backend");
  const venvPython = path.join(backend, ".venv", "Scripts", "python.exe");
  const python = existsSync(venvPython) ? venvPython : "python";
  const created = spawnSync(python, ["-m", "app.create_user", "--email", email], {
    cwd: backend,
    input: `${password}\n`,
    encoding: "utf8",
  });
  if (created.status !== 0) {
    const detail = `${created.stderr ?? ""}\n${created.stdout ?? ""}`.replaceAll(password, "[omisso]");
    throw new Error(`Não foi possível criar a conta de teste. ${detail.trim()}`);
  }

  mkdirSync(path.dirname(credentialsPath), { recursive: true });
  mkdirSync(path.resolve(process.cwd(), "..", "docs", "evidencias", "I5.1", "capturas"), {
    recursive: true,
  });
  mkdirSync(path.resolve(process.cwd(), "..", "docs", "evidencias", "I5.2", "capturas"), {
    recursive: true,
  });
  mkdirSync(path.resolve(process.cwd(), "..", "docs", "evidencias", "I5.3", "capturas"), {
    recursive: true,
  });
  mkdirSync(path.resolve(process.cwd(), "..", "docs", "evidencias", "I5.4", "capturas"), {
    recursive: true,
  });
  writeFileSync(credentialsPath, JSON.stringify({ email, password }), {
    encoding: "utf8",
    mode: 0o600,
  });
}
