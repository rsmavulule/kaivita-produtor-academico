import { spawnSync } from "node:child_process";
import path from "node:path";

import { hostApiUrl, hostWebUrl } from "./support";

export async function recoverApi(): Promise<void> {
  const root = path.resolve(process.cwd(), "..");
  spawnSync("docker", ["compose", "start", "api"], { cwd: root, encoding: "utf8" });
  await waitFor(
    () => {
      const probe = spawnSync("curl.exe", ["--noproxy", "*", "-fsS", `${hostApiUrl()}/health`], {
        encoding: "utf8",
      });
      return probe.status === 0 && probe.stdout.includes('"database":"up"');
    },
    "A API não ficou saudável depois da execução. Recupere com: docker compose start api",
  );
  // O processo Next.js guarda ligações ao contentor antigo. Reiniciá-lo
  // deita fora essas ligações depois de a API voltar a responder.
  spawnSync("docker", ["compose", "restart", "web"], { cwd: root, encoding: "utf8" });
  await waitFor(() => {
    const probe = spawnSync(
      "curl.exe",
      ["--noproxy", "*", "-fsS", "-o", "NUL", `${hostWebUrl()}/login`],
      { encoding: "utf8" },
    );
    return probe.status === 0;
  }, "A interface não ficou saudável depois da execução. Recupere com: docker compose restart web");
}

async function waitFor(ready: () => boolean, failure: string): Promise<void> {
  const deadline = Date.now() + 40_000;
  while (Date.now() < deadline) {
    if (ready()) return;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(failure);
}
