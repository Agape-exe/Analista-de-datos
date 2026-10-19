import { spawnSync } from "node:child_process";
import { relative, resolve } from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const cli = require.resolve("@playwright/test/cli");
const frontend = fileURLToPath(new URL("..", import.meta.url));
process.chdir(frontend);

// Discover through Playwright so new files and configured projects stay included.
const discovery = spawnSync(process.execPath, [cli, "test", "--list", "--reporter=json"], {
  encoding: "utf8", env: process.env,
});
if (discovery.error || discovery.status !== 0) {
  console.error(discovery.error ?? discovery.stderr ?? discovery.stdout);
  process.exit(1);
}
const report = JSON.parse(discovery.stdout);
const files = [...new Set(report.suites.map((suite) => suite.file))];
if (!files.length) throw new Error("Playwright did not discover any test files");
if (process.argv.includes("--list")) {
  console.log(files.join("\n"));
  process.exit(0);
}

const failures = [];
for (const file of files) {
  const name = relative(frontend, resolve(report.config.rootDir, file)).replaceAll("\\", "/");
  const artifactName = name.replaceAll(/[^a-zA-Z0-9_-]/g, "_");
  const output = resolve("test-results", artifactName);
  // A fresh Playwright process starts fresh Uvicorn/Vite servers for this file.
  // Keep real quotas, all assertions and all failures; no retries or guard bypass.
  const pattern = name.replaceAll(/[.*+?^${}()|[\]\\]/g, "\\$&");
  console.log(`\nE2E isolated file: ${name}`);
  const run = spawnSync(process.execPath, [cli, "test", pattern, `--output=${output}`], {
    stdio: "inherit",
    env: {
      ...process.env,
      PLAYWRIGHT_HTML_OUTPUT_DIR: resolve("playwright-report", artifactName),
      PLAYWRIGHT_JUNIT_OUTPUT_FILE: resolve(output, "e2e.xml"),
    },
  });
  if (run.error || run.status !== 0) {
    console.error(run.error ?? `Failed: ${name} (exit ${run.status}, signal ${run.signal})`);
    failures.push(name);
  }
}
console.log(`\nE2E files: ${files.length}; failed files: ${failures.length}`);
if (failures.length) console.error(failures.join("\n"));
process.exitCode = failures.length ? 1 : 0;
