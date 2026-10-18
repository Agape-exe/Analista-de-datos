import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RequestGate } from "./request-gate";

const flush = () => new Promise<void>((resolve) => queueMicrotask(resolve));

describe("RequestGate", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("runs at most `limit` requests at once and starts the next in order", async () => {
    const gate = new RequestGate(2);
    const started: number[] = [];
    const releases = await Promise.all([gate.acquire(), gate.acquire()]);
    void gate.acquire().then(() => started.push(3));
    void gate.acquire().then(() => started.push(4));
    await flush();
    expect(started).toEqual([]);

    releases[0]();
    releases[0]();
    await flush();
    expect(started).toEqual([3]);
  });

  it("drops aborted waiters without starting them", async () => {
    const gate = new RequestGate(1);
    const release = await gate.acquire();
    const controller = new AbortController();
    const queued = gate.acquire(controller.signal);
    const next = vi.fn();
    void gate.acquire().then(next);

    controller.abort();
    await expect(queued).rejects.toBeDefined();
    release();
    await flush();
    expect(next).toHaveBeenCalledOnce();
  });

  it("rejects immediately when the signal is already aborted", async () => {
    const controller = new AbortController();
    controller.abort();
    await expect(new RequestGate(1).acquire(controller.signal)).rejects.toBeDefined();
  });

  it("holds queued requests until the cooldown ends and lets retries jump the queue", async () => {
    const gate = new RequestGate(1);
    gate.pause(2_000);
    const order: string[] = [];
    void gate.acquire().then((release) => { order.push("first"); release(); });
    void gate.acquire(undefined, { priority: true }).then((release) => { order.push("retry"); release(); });

    await vi.advanceTimersByTimeAsync(1_999);
    expect(order).toEqual([]);
    expect(gate.remainingPause()).toBe(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(order).toEqual(["retry", "first"]);
  });
});
