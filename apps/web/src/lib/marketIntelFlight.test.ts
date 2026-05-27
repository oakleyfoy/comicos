import { describe, it, expect, beforeEach } from "vitest";
import { dedupedFlight, resetDedupedFlightForTests } from "./marketIntelFlight";

describe("dedupedFlight", () => {
  beforeEach(() => resetDedupedFlightForTests());

  it("merges overlapping async work for identical keys into a single invocation", async () => {
    let calls = 0;
    async function probe(): Promise<number> {
      return dedupedFlight("key-a", async () => {
        calls += 1;
        await Promise.resolve();
        return calls;
      });
    }

    const [first, second] = await Promise.all([probe(), probe()]);
    expect(first).toBe(1);
    expect(second).toBe(1);
    expect(calls).toBe(1);
  });
});
