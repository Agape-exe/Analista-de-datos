import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RequestGate } from "./request-gate";

const flush = () => vi.advanceTimersByTimeAsync(0);

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

  it("orders requests issued together by priority, FIFO within a level", async () => {
    const gate = new RequestGate(1);
    const order: string[] = [];
    const run = (name: string, priority: number) => void gate.acquire(undefined, { priority })
      .then((release) => { order.push(name); release(); });
    // Same synchronous batch, as React runs child effects before parent effects.
    run("histogram", 1);
    run("outliers", 2);
    run("boxplot", 1);
    run("ranking", 0);
    await flush();
    expect(order).toEqual(["ranking", "histogram", "boxplot", "outliers"]);
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

  it("can reject every queued request at once", async () => {
    const gate = new RequestGate(1);
    const release = await gate.acquire();
    const queued = [gate.acquire(), gate.acquire()];
    gate.failQueued(() => new Error("límite"));
    await expect(Promise.all(queued)).rejects.toThrow("límite");
    release();
    await expect(gate.acquire()).resolves.toBeTypeOf("function");
  });

  it("rejects immediately when the signal is already aborted", async () => {
    const controller = new AbortController();
    controller.abort();
    await expect(new RequestGate(1).acquire(controller.signal)).rejects.toBeDefined();
  });

  it("only takes a slot synchronously when nothing is waiting", () => {
    const gate = new RequestGate(1);
    const release = gate.tryAcquire();
    expect(release).not.toBeNull();
    expect(gate.tryAcquire()).toBeNull();
    release?.();
    void gate.acquire();
    expect(gate.tryAcquire()).toBeNull();
  });

  it("holds queued requests until the cooldown ends and lets retries jump the queue", async () => {
    const gate = new RequestGate(1);
    gate.pause(2_000);
    const order: string[] = [];
    void gate.acquire().then((release) => { order.push("first"); release(); });
    void gate.acquire(undefined, { priority: -1 }).then((release) => { order.push("retry"); release(); });

    await vi.advanceTimersByTimeAsync(1_999);
    expect(order).toEqual([]);
    expect(gate.remainingPause()).toBe(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(order).toEqual(["retry", "first"]);
  });
});
