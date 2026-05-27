import { describe, it, expect } from "vitest";
import type { MarketApiV1Meta } from "../api/client";
import { buildMarketSnapshotChainIssues, checksumAlignedWithEnvelope } from "./marketIntelTrace";

describe("buildMarketSnapshotChainIssues", () => {
  it("reports misaligned deterministic snapshot chain", () => {
    const issues = buildMarketSnapshotChainIssues({
      score: { id: 10 } as never,
      signal: { id: 2, market_acquisition_score_snapshot_id: 999 } as never,
      opportunity: null,
      coupling: null,
    });
    expect(issues.some((m) => m.includes("Latest signal snapshot"))).toBe(true);
  });

  it("returns empty when lineage matches", () => {
    expect(
      buildMarketSnapshotChainIssues({
        score: { id: 10 } as never,
        signal: { id: 2, market_acquisition_score_snapshot_id: 10 } as never,
        opportunity: { id: 3, market_acquisition_signal_snapshot_id: 2 } as never,
        coupling: { id: 4, market_acquisition_opportunity_snapshot_id: 3 } as never,
      }),
    ).toEqual([]);
  });
});

describe("checksumAlignedWithEnvelope", () => {
  it("treats missing envelope checksum as pass-through", () => {
    const meta = { checksum: null } as unknown as MarketApiV1Meta;
    expect(checksumAlignedWithEnvelope(meta, "abc")).toBe(true);
  });

  it("requires matching row checksum when envelope supplies checksum", () => {
    const meta = {
      checksum: "same",
      owner_user_id: "1",
      snapshot_id: "1",
      generated_at: "2026-01-01T00:00:00Z",
      engine_versions: {},
    } as MarketApiV1Meta;
    expect(checksumAlignedWithEnvelope(meta, "same")).toBe(true);
    expect(checksumAlignedWithEnvelope(meta, "different")).toBe(false);
  });
});
