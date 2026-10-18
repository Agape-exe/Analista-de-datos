import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { capacityDelay, getDatasetQuality, RateLimitedError, requestGate, retryAfterMs, runTool } from "./api-client";

const success = { method: "outliers", status: "SUCCESS", result: {}, completeness: "complete" };
const ok = () => new Response(JSON.stringify(success), { status: 200 });
const limited = (retryAfter: string | null, code = "REQUEST_RATE_LIMITED") => new Response(
  JSON.stringify({ detail: { code, message: "Too many requests. Try again later." } }),
  { status: 429, headers: retryAfter === null ? {} : { "Retry-After": retryAfter } },
);
const busy = (retryAfter: string | null = "1") => limited(retryAfter, "ANALYSIS_CAPACITY_EXCEEDED");
const call = (signal?: AbortSignal) => runTool("ds", "outliers", { variables: ["x"], parameters: {} }, signal);

describe("API transport", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(Math, "random").mockReturnValue(0.5);
    requestGate.reset();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    requestGate.reset();
  });

  it("sends one request at a time, matching the production capacity", async () => {
    const pending: Array<(response: Response) => void> = [];
    const fetch = vi.fn(() => new Promise<Response>((resolve) => pending.push(resolve)));
    vi.stubGlobal("fetch", fetch);

    const results = [call(), call(), call()];
    await vi.advanceTimersByTimeAsync(0);
    expect(fetch).toHaveBeenCalledTimes(1);
    pending[0](ok());
    await vi.advanceTimersByTimeAsync(0);
    expect(fetch).toHaveBeenCalledTimes(2);
    pending[1](ok());
    await vi.advanceTimersByTimeAsync(0);
    pending[2](ok());
    await expect(Promise.all(results)).resolves.toHaveLength(3);
  });

  it("never sends a request cancelled while it was queued", async () => {
    const pending: Array<(response: Response) => void> = [];
    const fetch = vi.fn(() => new Promise<Response>((resolve) => pending.push(resolve)));
    vi.stubGlobal("fetch", fetch);
    const controller = new AbortController();

    void call();
    const cancelled = call(controller.signal);
    await vi.advanceTimersByTimeAsync(0);
    controller.abort();
    await expect(cancelled).rejects.toBeDefined();
    pending[0](ok());
    await vi.advanceTimersByTimeAsync(0);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("keeps the slot of a cancelled tool request until the server answers", async () => {
    const pending: Array<(response: Response) => void> = [];
    const fetch = vi.fn<(url: string, init: RequestInit) => Promise<Response>>(() => new Promise<Response>((resolve) => pending.push(resolve)));
    vi.stubGlobal("fetch", fetch);
    const controller = new AbortController();

    const first = call(controller.signal);
    await vi.advanceTimersByTimeAsync(0);
    expect(fetch.mock.calls[0][1].signal).toBeUndefined();
    const next = call();
    controller.abort();
    await expect(first).rejects.toBeDefined();
    await vi.advanceTimersByTimeAsync(0);
    expect(fetch).toHaveBeenCalledTimes(1);

    pending[0](ok());
    await vi.advanceTimersByTimeAsync(0);
    expect(fetch).toHaveBeenCalledTimes(2);
    pending[1](ok());
    await expect(next).resolves.toEqual({ tool: "outliers" });
  });

  it("backs off exponentially when the analysis capacity is busy, then recovers", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(busy()).mockResolvedValueOnce(busy()).mockResolvedValueOnce(ok());
    vi.stubGlobal("fetch", fetch);

    const result = call();
    await vi.advanceTimersByTimeAsync(999);
    expect(fetch).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(fetch).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(1_999);
    expect(fetch).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(1);
    await expect(result).resolves.toEqual({ tool: "outliers" });
    expect(fetch).toHaveBeenCalledTimes(3);
  });

  it("gives up on a persistently busy server after a bounded number of attempts", async () => {
    const fetch = vi.fn(() => Promise.resolve(busy()));
    vi.stubGlobal("fetch", fetch);

    const result = call();
    const assertion = expect(result).rejects.toThrow("El servicio de análisis está ocupado");
    await vi.advanceTimersByTimeAsync(60_000);
    await assertion;
    expect(fetch).toHaveBeenCalledTimes(5);
  });

  it("fails fast when a busy server asks for a long wait", async () => {
    const fetch = vi.fn(() => Promise.resolve(busy("30")));
    vi.stubGlobal("fetch", fetch);
    await expect(call()).rejects.toMatchObject({ code: "ANALYSIS_CAPACITY_EXCEEDED", retryAfterSeconds: 30 });
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("waits for Retry-After before retrying a rate-limited request", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(limited("2")).mockResolvedValueOnce(ok());
    vi.stubGlobal("fetch", fetch);

    const result = call();
    await vi.advanceTimersByTimeAsync(1_999);
    expect(fetch).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    await expect(result).resolves.toEqual(success);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("fails fast on long rate-limit waits and keeps later requests from hitting the server", async () => {
    const fetch = vi.fn(() => Promise.resolve(limited("45")));
    vi.stubGlobal("fetch", fetch);

    const first = call();
    await expect(first).rejects.toBeInstanceOf(RateLimitedError);
    await expect(first).rejects.toThrow("Inténtalo de nuevo en 45 s");
    await expect(call()).rejects.toMatchObject({ code: "REQUEST_RATE_LIMITED", retryAfterSeconds: 45 });
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("applies the cooldown before a queued request can use the freed slot", async () => {
    const fetch = vi.fn(() => Promise.resolve(limited("45")));
    vi.stubGlobal("fetch", fetch);

    const results = [call(), call()];
    await expect(results[0]).rejects.toMatchObject({ retryAfterSeconds: 45 });
    await expect(results[1]).rejects.toBeInstanceOf(RateLimitedError);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("does not retry in bursts when Retry-After cannot be read", async () => {
    const fetch = vi.fn(() => Promise.resolve(limited(null)));
    vi.stubGlobal("fetch", fetch);

    await expect(call()).rejects.toMatchObject({ retryAfterSeconds: null, message: expect.stringContaining("en unos segundos") });
    await expect(getDatasetQuality("ds")).rejects.toBeInstanceOf(RateLimitedError);
    expect(fetch).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(15_000);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok()));
    await expect(call()).resolves.toEqual({ tool: "outliers" });
  });

  it("reads Retry-After as seconds or an HTTP date and reports unreadable values", () => {
    const now = Date.parse("2026-10-18T12:00:00Z");
    expect(retryAfterMs("3", now)).toBe(3_000);
    expect(retryAfterMs("Sun, 18 Oct 2026 12:00:05 GMT", now)).toBe(5_000);
    expect(retryAfterMs(null, now)).toBeNull();
    expect(retryAfterMs("soon", now)).toBeNull();
  });

  it("jitters the capacity backoff within ±20 % and never undercuts Retry-After", () => {
    expect(capacityDelay(0, null, () => 0)).toBe(800);
    expect(capacityDelay(0, null, () => 1)).toBe(1_200);
    expect(capacityDelay(3, null, () => 0.5)).toBe(8_000);
    expect(capacityDelay(9, null, () => 0.5)).toBe(8_000);
    expect(capacityDelay(0, 5_000, () => 0.5)).toBe(5_000);
  });
});
