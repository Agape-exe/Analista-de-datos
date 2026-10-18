type Release = () => void;

interface Waiter {
  priority: number;
  start: () => void;
  fail: (reason: unknown) => void;
}

/**
 * Client-side counterpart of the backend's operation capacity: lets at most `limit`
 * requests run at once, queues the rest by priority (lower first, FIFO within a level)
 * and honours a shared cooldown (Retry-After) so queued work does not hit the server
 * while it is throttling us. Aborting a queued request removes it before it is sent.
 */
export class RequestGate {
  private active = 0;
  private resumeAt = 0;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private scheduled = false;
  private queue: Waiter[] = [];

  constructor(private readonly limit: number) {}

  /** Takes a free slot synchronously when nothing is queued or cooling down. */
  tryAcquire(): Release | null {
    if (this.active >= this.limit || this.queue.length > 0 || this.remainingPause() > 0) return null;
    return this.take();
  }

  /**
   * Queues a request. Starting is deferred to a microtask so every request issued in the
   * same render (React runs child effects before parent effects) is ordered by priority.
   */
  acquire(signal?: AbortSignal, { priority = 0 } = {}): Promise<Release> {
    return new Promise((resolve, reject) => {
      if (signal?.aborted) {
        reject(signal.reason);
        return;
      }
      const onAbort = () => {
        this.queue = this.queue.filter((item) => item !== waiter);
        reject(signal?.reason);
      };
      const waiter: Waiter = {
        priority,
        start: () => {
          signal?.removeEventListener("abort", onAbort);
          resolve(this.take());
        },
        fail: (reason) => {
          signal?.removeEventListener("abort", onAbort);
          reject(reason);
        },
      };
      signal?.addEventListener("abort", onAbort, { once: true });
      const index = this.queue.findIndex((item) => item.priority > priority);
      if (index === -1) this.queue.push(waiter);
      else this.queue.splice(index, 0, waiter);
      this.schedule();
    });
  }

  /** Holds every queued request until `ms` from now (keeps the latest deadline). */
  pause(ms: number) {
    this.resumeAt = Math.max(this.resumeAt, Date.now() + ms);
  }

  /** Rejects every queued request, e.g. when the cooldown is too long to wait silently. */
  failQueued(reason: () => unknown) {
    const waiting = this.queue;
    this.queue = [];
    waiting.forEach((waiter) => waiter.fail(reason()));
  }

  /** Milliseconds left in the current cooldown, 0 when requests may be sent. */
  remainingPause(): number {
    return Math.max(0, this.resumeAt - Date.now());
  }

  reset() {
    if (this.timer) clearTimeout(this.timer);
    this.timer = undefined;
    this.scheduled = false;
    this.resumeAt = 0;
    this.active = 0;
    this.queue = [];
  }

  private take(): Release {
    this.active += 1;
    let released = false;
    return () => {
      if (released) return;
      released = true;
      this.active -= 1;
      this.schedule();
    };
  }

  private schedule() {
    if (this.scheduled) return;
    this.scheduled = true;
    queueMicrotask(() => {
      this.scheduled = false;
      this.drain();
    });
  }

  private drain() {
    const wait = this.remainingPause();
    if (wait > 0) {
      if (this.timer) clearTimeout(this.timer);
      this.timer = setTimeout(() => {
        this.timer = undefined;
        this.drain();
      }, wait);
      return;
    }
    while (this.active < this.limit && this.queue.length > 0) {
      this.queue.shift()?.start();
    }
  }
}
