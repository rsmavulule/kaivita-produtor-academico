import { defineConfig, devices } from "@playwright/test";

import { appOrigin, hostApiUrl } from "./e2e/support";

const baseURL = appOrigin;
const port = new URL(baseURL).port || "3100";

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  globalTeardown: "./e2e/global-teardown.ts",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 20_000 },
  reporter: "list",
  use: {
    ...devices["Desktop Chrome"],
    baseURL,
    trace: "off",
    video: "off",
    screenshot: "off",
  },
  webServer: process.env.E2E_NO_SERVER
    ? undefined
    : {
        command: `npx next dev --hostname 127.0.0.1 --port ${port}`,
        url: baseURL,
        reuseExistingServer: false,
        env: {
          ...process.env,
          API_URL: hostApiUrl(),
        },
      },
});
