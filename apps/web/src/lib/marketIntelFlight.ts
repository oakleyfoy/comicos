/** In-flight request coalescing (React Strict Mode + parallel mounts → one network round-trip per key). */
const inflight = new Map<string, Promise<unknown>>();

export async function dedupedFlight<T>(key: string, run: () => Promise<T>): Promise<T> {
  const existing = inflight.get(key) as Promise<T> | undefined;
  if (existing) {
    return existing;
  }
  const pending = run().finally(() => {
    inflight.delete(key);
  });
  inflight.set(key, pending);
  return pending as Promise<T>;
}

/** Clears tracked in-flight promises (Vitest isolation). */
export function resetDedupedFlightForTests(): void {
  inflight.clear();
}
