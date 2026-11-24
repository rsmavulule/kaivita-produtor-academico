import { cleanupRunAccounts } from "./cleanup";
import { recoverApi } from "./recover";
import { releaseRunLock } from "./run-lock";

export default async function globalTeardown(): Promise<void> {
  let recoveryFailed = false;
  try {
    await recoverApi();
  } catch {
    recoveryFailed = true;
  }
  try {
    cleanupRunAccounts();
  } finally {
    releaseRunLock();
  }
  if (recoveryFailed) {
    throw new Error("A API não ficou saudável depois da execução. Recupere com: docker compose start api");
  }
}
