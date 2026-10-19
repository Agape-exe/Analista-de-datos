import { test as base, expect, type Request, type Response } from "@playwright/test";

// Observe real HTTP traffic without routing, delaying or retrying requests.
export const test = base.extend<{ apiDiagnostics: void }>({
  apiDiagnostics: [async ({ page }, use, testInfo) => {
    const started = performance.now();
    const requests = new Map<Request, number>();
    const events: Record<string, unknown>[] = [];
    const pending: Promise<void>[] = [];
    const record = (event: Record<string, unknown>) => {
      events.push({ milliseconds: performance.now() - started, ...event });
    };
    const onRequest = (request: Request) => {
      const path = new URL(request.url()).pathname;
      if (!path.startsWith("/api/")) return;
      const id = requests.size + 1;
      requests.set(request, id);
      record({ event: "request", id, method: request.method(), path,
        // Tool parameters identify concurrent work; never record upload bodies.
        parameters: path.includes("/tools/") ? request.postData() : undefined });
    };
    const onResponse = (response: Response) => {
      const id = requests.get(response.request());
      if (!id) return;
      record({ event: "response", id, status: response.status(),
        retryAfter: response.headers()["retry-after"] });
      if (response.status() >= 400) pending.push((async () => {
        try { record({ event: "error-body", id, body: await response.text() }); }
        catch { record({ event: "error-body-unavailable", id }); }
      })());
    };
    const onFailed = (request: Request) => {
      const id = requests.get(request);
      if (id) record({ event: "requestfailed", id, failure: request.failure() });
    };
    page.on("request", onRequest);
    page.on("response", onResponse);
    page.on("requestfailed", onFailed);
    await use();
    page.off("request", onRequest);
    page.off("response", onResponse);
    page.off("requestfailed", onFailed);
    await Promise.all(pending);
    await testInfo.attach("api-timeline", {
      body: JSON.stringify(events, null, 2), contentType: "application/json",
    });
  }, { auto: true }],
});

export { expect };
