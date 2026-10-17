import { defineConfig } from "@playwright/test";

const backendPort = Number(process.env.E2E_BACKEND_PORT || 8016);
const frontendPort = Number(process.env.E2E_FRONTEND_PORT || 5186);
const backendURL = `http://127.0.0.1:${backendPort}`;
const frontendURL = `http://127.0.0.1:${frontendPort}`;

export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  reporter: "list",
  use: {
    baseURL: frontendURL,
    browserName: "chromium",
    channel: process.env.PLAYWRIGHT_CHANNEL || "chromium",
    viewport: { width: 1440, height: 1000 },
  },
  webServer: [
    {
      command: `uv run python -m uvicorn app.api.main:app --host 127.0.0.1 --port ${backendPort}`,
      cwd: "..",
      url: `${backendURL}/health`,
      reuseExistingServer: false,
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort} --strictPort`,
      env: { API_PROXY_TARGET: backendURL },
      url: frontendURL,
      reuseExistingServer: false,
    },
  ],
});
