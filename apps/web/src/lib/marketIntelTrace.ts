import type {
  MarketAcquisitionOpportunitySnapshotRead,
  MarketAcquisitionScoreSnapshotRead,
  MarketAcquisitionSignalSnapshotRead,
  MarketApiV1Meta,
  PortfolioMarketCouplingSnapshotRead,
} from "../api/client";

export type MarketIntelTraceEnds = {
  score: MarketAcquisitionScoreSnapshotRead | null;
  signal: MarketAcquisitionSignalSnapshotRead | null;
  opportunity: MarketAcquisitionOpportunitySnapshotRead | null;
  coupling: PortfolioMarketCouplingSnapshotRead | null;
};

/** Cross-layer FK alignment for latest rows returned by dashboard list calls. */
export function buildMarketSnapshotChainIssues(ends: MarketIntelTraceEnds): string[] {
  const issues: string[] = [];
  const { score, signal, opportunity, coupling } = ends;

  if (score && signal && signal.market_acquisition_score_snapshot_id !== score.id) {
    issues.push("Latest signal snapshot is not keyed to the latest score snapshot id.");
  }

  if (signal && opportunity && opportunity.market_acquisition_signal_snapshot_id !== signal.id) {
    issues.push("Latest opportunity snapshot does not reference the latest signal snapshot id.");
  }

  if (opportunity && coupling && coupling.market_acquisition_opportunity_snapshot_id !== opportunity.id) {
    issues.push("Latest coupling snapshot does not reference the latest opportunity snapshot id.");
  }

  return issues;
}

/**
 * Validates row checksum vs envelope checksum when meta.checksum is present (detail/single-object responses).
 * Aggregated standard-list envelopes typically omit checksum — those pass as `true`.
 */
export function checksumAlignedWithEnvelope(meta: MarketApiV1Meta | null, rowChecksum: string | null | undefined): boolean {
  if (!meta?.checksum) {
    return true;
  }
  if (!rowChecksum) {
    return false;
  }
  return meta.checksum === rowChecksum;
}
