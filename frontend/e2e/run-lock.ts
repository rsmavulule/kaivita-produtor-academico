import { closeSync, existsSync, openSync, readFileSync, unlinkSync, writeSync } from "node:fs";
import path from "node:path";

const lockPath = path.join(process.cwd(), "e2e", ".run.lock");

type LockRecord = { pid: number; startedAt: string };

export function acquireRunLock(): void {
  const stale = existingLock();
  if (stale && processAlive(stale.pid) && stale.pid !== process.pid) {
    throw new Error(
      `Já existe uma execução Playwright no processo ${stale.pid}, desde ${stale.startedAt}. Espere que termine. Se esse processo já não existir, apague frontend/e2e/.run.lock.`,
    );
  }
  if (existsSync(lockPath)) unlinkSync(lockPath);
  const fd = openSync(lockPath, "wx");
  try {
    writeSync(fd, JSON.stringify({ pid: process.pid, startedAt: new Date().toISOString() }));
  } finally {
    closeSync(fd);
  }
}

export function releaseRunLock(): void {
  const current = existingLock();
  if (!current || current.pid !== process.pid) return;
  unlinkSync(lockPath);
}

function existingLock(): LockRecord | null {
  if (!existsSync(lockPath)) return null;
  try {
    const parsed = JSON.parse(readFileSync(lockPath, "utf8")) as Partial<LockRecord>;
    if (typeof parsed.pid !== "number" || typeof parsed.startedAt !== "string") return null;
    return { pid: parsed.pid, startedAt: parsed.startedAt };
  } catch {
    return null;
  }
}

function processAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}
