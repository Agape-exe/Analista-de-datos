import { defineConfig } from "@playwright/test";

const backendPort = Number(process.env.E2E_BACKEND_PORT || 8016);
const frontendPort = Number(process.env.E2E_FRONTEND_PORT || 5186);
const backendURL = `http://127.0.0.1:${backendPort}`;
const frontendURL = `http://127.0.0.1:${frontendPort}`;

export default defineConfig({
  testDir: "./e2e",
  forbidOnly: !!process.env.CI,
  workers: 1,
  reporter: process.env.CI
    ? [["list"], ["html", { open: "never" }], ["junit", { outputFile: "test-results/e2e.xml" }]]
    : "list",
  use: {
    baseURL: frontendURL,
    browserName: "chromium",
    channel: process.env.PLAYWRIGHT_CHANNEL || "chromium",
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: `uv run python -m uvicorn app.api.main:app --host 127.0.0.1 --port ${backendPort}`,
      cwd: "..",
      env: {
        UV_LOCKED: "true",
        MDA_DEPLOYMENT__ENVIRONMENT: "development",
        MDA_DEPLOYMENT__ALLOW_LOCAL_ANALYSIS: "true",
        MDA_PERSISTENCE__DATABASE_URL: "sqlite:///:memory:",
        MDA_LLM__PROVIDER: "disabled",
        MDA_UPLOADS__MAX_DATASET_BYTES: "2097152",
      },
      url: `${backendURL}/health`,
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort} --strictPort`,
      env: { API_PROXY_TARGET: backendURL },
      url: frontendURL,
      timeout: 120_000,
      reuseExistingServer: false,
    },
  ],
});
