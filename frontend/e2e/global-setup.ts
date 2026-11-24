import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

import { cleanupRunAccounts } from "./cleanup";
import { rememberAccount, resetManifest } from "./manifest";
import { releaseRunLock, acquireRunLock } from "./run-lock";

export const credentialsPath = path.join(process.cwd(), "e2e", ".credentials.json");

export default function globalSetup() {
  acquireRunLock();
  try {
    prepareAccount();
  } catch (error) {
    releaseRunLock();
    throw error;
  }
}

function prepareAccount() {
  const email = `i51-${Date.now()}@example.com`;
  const password = randomBytes(18).toString("base64url");
  const backend = path.resolve(process.cwd(), "..", "backend");
  const venvPython = path.join(backend, ".venv", "Scripts", "python.exe");
  const python = existsSync(venvPython) ? venvPython : "python";
  // A execução anterior pode ter morrido com o manifesto ainda escrito.
  // Essas contas saem antes de o ficheiro ser substituído. O email novo
  // fica registado antes de a conta existir, para a próxima limpeza o ver.
  cleanupRunAccounts();
  resetManifest();
  rememberAccount(email);
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
  mkdirSync(path.resolve(process.cwd(), "test-results", "capturas"), { recursive: true });
  writeFileSync(credentialsPath, JSON.stringify({ email, password }), {
    encoding: "utf8",
    mode: 0o600,
  });
}
