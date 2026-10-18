import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RateLimitedError, requestGate, retryAfterMs, runTool } from "./api-client";

const ok = () => new Response(JSON.stringify({ tool: "outliers" }), { status: 200 });
const limited = (retryAfter: string | null, code = "REQUEST_RATE_LIMITED") => new Response(
  JSON.stringify({ detail: { code, message: "Too many requests. Try again later." } }),
  { status: 429, headers: retryAfter === null ? {} : { "Retry-After": retryAfter } },
);
const call = (signal?: AbortSignal) => runTool("ds", "outliers", { variables: ["x"], parameters: {} }, signal);

describe("API transport", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    requestGate.reset();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    requestGate.reset();
  });

  it("sends at most two requests at a time", async () => {
    const pending: Array<(response: Response) => void> = [];
    const fetch = vi.fn(() => new Promise<Response>((resolve) => pending.push(resolve)));
    vi.stubGlobal("fetch", fetch);

    const results = [call(), call(), call()];
    await vi.advanceTimersByTimeAsync(0);
    expect(fetch).toHaveBeenCalledTimes(2);

    pending[0](ok());
    await vi.advanceTimersByTimeAsync(0);
    expect(fetch).toHaveBeenCalledTimes(3);
    pending[1](ok());
    pending[2](ok());
    await expect(Promise.all(results)).resolves.toHaveLength(3);
  });

  it("never sends a request cancelled while it was queued", async () => {
    const pending: Array<(response: Response) => void> = [];
    const fetch = vi.fn(() => new Promise<Response>((resolve) => pending.push(resolve)));
    vi.stubGlobal("fetch", fetch);
    const controller = new AbortController();

    void call();
    void call();
    const cancelled = call(controller.signal);
    controller.abort();
    await expect(cancelled).rejects.toBeDefined();
    pending[0](ok());
    await vi.advanceTimersByTimeAsync(0);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("waits for Retry-After before retrying a throttled request", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(limited("2")).mockResolvedValueOnce(ok());
    vi.stubGlobal("fetch", fetch);

    const result = call();
    await vi.advanceTimersByTimeAsync(1_999);
    expect(fetch).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    await expect(result).resolves.toEqual({ tool: "outliers" });
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("gives up after a bounded number of retries", async () => {
    const fetch = vi.fn(() => Promise.resolve(limited("1", "ANALYSIS_CAPACITY_EXCEEDED")));
    vi.stubGlobal("fetch", fetch);

    const result = call();
    const assertion = expect(result).rejects.toThrow("El servicio de análisis está ocupado");
    await vi.advanceTimersByTimeAsync(10_000);
    await assertion;
    expect(fetch).toHaveBeenCalledTimes(4);
  });

  it("fails fast on long waits and keeps later requests from hitting the server", async () => {
    const fetch = vi.fn(() => Promise.resolve(limited("45")));
    vi.stubGlobal("fetch", fetch);

    const first = call();
    await expect(first).rejects.toBeInstanceOf(RateLimitedError);
    await expect(first).rejects.toThrow("Inténtalo de nuevo en 45 s");
    await expect(call()).rejects.toMatchObject({ code: "REQUEST_RATE_LIMITED", retryAfterSeconds: 45 });
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("reads Retry-After as seconds or an HTTP date", () => {
    const now = Date.parse("2026-10-18T12:00:00Z");
    expect(retryAfterMs("3", now)).toBe(3_000);
    expect(retryAfterMs("Sun, 18 Oct 2026 12:00:05 GMT", now)).toBe(5_000);
    expect(retryAfterMs(null, now)).toBe(1_000);
    expect(retryAfterMs("soon", now)).toBe(1_000);
  });
});
