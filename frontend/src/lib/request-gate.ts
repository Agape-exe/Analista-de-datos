type Release = () => void;

interface Waiter {
  start: () => void;
}

/**
 * Client-side counterpart of the backend's operation capacity: lets at most `limit`
 * requests run at once, queues the rest in order and honours a shared cooldown
 * (Retry-After) so queued work does not hit the server while it is throttling us.
 * Aborting a queued request removes it before it is ever sent.
 */
export class RequestGate {
  private active = 0;
  private resumeAt = 0;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private queue: Waiter[] = [];

  constructor(private readonly limit: number) {}

  /** Takes a free slot synchronously when nothing is queued or cooling down. */
  tryAcquire(): Release | null {
    if (this.active >= this.limit || this.queue.length > 0 || this.remainingPause() > 0) return null;
    return this.take();
  }

  acquire(signal?: AbortSignal, { priority = false } = {}): Promise<Release> {
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
        start: () => {
          signal?.removeEventListener("abort", onAbort);
          resolve(this.take());
        },
      };
      signal?.addEventListener("abort", onAbort, { once: true });
      if (priority) this.queue.unshift(waiter);
      else this.queue.push(waiter);
      this.drain();
    });
  }

  /** Holds every queued request until `ms` from now (keeps the latest deadline). */
  pause(ms: number) {
    this.resumeAt = Math.max(this.resumeAt, Date.now() + ms);
  }

  /** Milliseconds left in the current cooldown, 0 when requests may be sent. */
  remainingPause(): number {
    return Math.max(0, this.resumeAt - Date.now());
  }

  reset() {
    if (this.timer) clearTimeout(this.timer);
    this.timer = undefined;
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
      this.drain();
    };
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
