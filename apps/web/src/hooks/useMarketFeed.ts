import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, fetchMarketV1Envelope, type MarketApiV1Meta, type MarketApiV1Pagination } from "../api/client";
import { dedupedFlight } from "../lib/marketIntelFlight";

export type MarketFeedEventRead = {
  id: number;
  owner_user_id: number | null;
  event_type: string;
  severity: string;
  event_sequence_id: number;
  ingestion_batch_id?: number | null;
  normalization_run_id?: number | null;
  scoring_run_id?: number | null;
  signal_snapshot_id?: number | null;
  opportunity_snapshot_id?: number | null;
  coupling_snapshot_id?: number | null;
  event_payload_json: Record<string, unknown>;
  event_checksum: string;
  snapshot_date: string;
  created_at: string;
};

export type MarketFeedSnapshotRead = {
  id: number;
  owner_user_id: number | null;
  total_events: number;
  latest_event_sequence_id: number;
  latest_event_id?: number | null;
  latest_events_json: Record<string, unknown>;
  owner_timeline_json: Array<Record<string, unknown>>;
  event_type_counts_json: Record<string, number>;
  severity_counts_json: Record<string, number>;
  activity_heatmap_json: Record<string, Record<string, number>>;
  failure_clustering_json: Record<string, number>;
  snapshot_checksum: string;
  snapshot_date: string;
  created_at: string;
};

export type MarketFeedEventListResponse = {
  items: MarketFeedEventRead[];
  pagination: MarketApiV1Pagination;
};

export type MarketFeedSnapshotListResponse = {
  items: MarketFeedSnapshotRead[];
  pagination: MarketApiV1Pagination;
};

export type MarketFeedState = {
  loading: boolean;
  error: string | null;
  events: MarketFeedEventListResponse | null;
  snapshots: MarketFeedSnapshotListResponse | null;
  meta: MarketApiV1Meta | null;
};

export type MarketFeedPanelMode = "dashboard" | "ops" | "teaser";

function idleState(): MarketFeedState {
  return { loading: false, error: null, events: null, snapshots: null, meta: null };
}

export function useMarketFeed(ownerUserId: number | undefined, mode: MarketFeedPanelMode): {
  state: MarketFeedState;
  reload: () => Promise<void>;
  latestEvent: MarketFeedEventRead | null;
  latestSnapshot: MarketFeedSnapshotRead | null;
} {
  const [state, setState] = useState<MarketFeedState>(idleState);

  const scopeKey = ownerUserId ?? "all";

  const load = useCallback(async () => {
    if (!ownerUserId) {
      setState(idleState());
      return;
    }

    await dedupedFlight(`p39feed:${scopeKey}:${mode}`, async () => {
      setState((prev) => ({ ...prev, loading: true, error: null }));
      try {
        const [eventsEnvelope, snapshotsEnvelope] = await Promise.all([
          fetchMarketV1Envelope<MarketFeedEventListResponse>("/market-feed/events?limit=8&offset=0"),
          fetchMarketV1Envelope<MarketFeedSnapshotListResponse>("/market-feed/snapshots?limit=4&offset=0"),
        ]);
        setState({
          loading: false,
          error: null,
          events: eventsEnvelope.data,
          snapshots: snapshotsEnvelope.data,
          meta: eventsEnvelope.meta,
        });
      } catch (err) {
        const message = err instanceof ApiError ? err.message : "Unable to load market feed.";
        setState((prev) => ({ ...prev, loading: false, error: message }));
      }
    });
  }, [mode, ownerUserId, scopeKey]);

  useEffect(() => {
    void load();
  }, [load]);

  const latestEvent = useMemo(() => state.events?.items[0] ?? null, [state.events]);
  const latestSnapshot = useMemo(() => state.snapshots?.items[0] ?? null, [state.snapshots]);

  return { state, reload: load, latestEvent, latestSnapshot };
}
