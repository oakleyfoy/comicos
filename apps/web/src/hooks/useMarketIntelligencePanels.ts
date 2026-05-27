import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  fetchMarketV1Envelope,
  type MarketApiV1Meta,
  type MarketAcquisitionIngestionBatchListResponse,
  type MarketAcquisitionOpportunitySnapshotListResponse,
  type MarketAcquisitionScoreSnapshotListResponse,
  type MarketAcquisitionSignalSnapshotListResponse,
  type MarketNormalizationRunListResponse,
  type PortfolioMarketCouplingSnapshotListResponse,
} from "../api/client";
import { dedupedFlight } from "../lib/marketIntelFlight";
import { buildMarketSnapshotChainIssues } from "../lib/marketIntelTrace";

export type MarketIntelLayerKey =
  | "ingestion"
  | "normalization"
  | "scoring"
  | "signals"
  | "opportunities"
  | "coupling";

export type MarketIntelPanelState<T> = {
  loading: boolean;
  error: string | null;
  data: T | null;
  meta: MarketApiV1Meta | null;
};

export type MarketIntelPanelsState = {
  ingestion: MarketIntelPanelState<MarketAcquisitionIngestionBatchListResponse>;
  normalization: MarketIntelPanelState<MarketNormalizationRunListResponse>;
  scoring: MarketIntelPanelState<MarketAcquisitionScoreSnapshotListResponse>;
  signals: MarketIntelPanelState<MarketAcquisitionSignalSnapshotListResponse>;
  opportunities: MarketIntelPanelState<MarketAcquisitionOpportunitySnapshotListResponse>;
  coupling: MarketIntelPanelState<PortfolioMarketCouplingSnapshotListResponse>;
};

function idlePanel<T>(): MarketIntelPanelState<T> {
  return { loading: false, error: null, data: null, meta: null };
}

function loadingPanel<T>(prev: MarketIntelPanelState<T>): MarketIntelPanelState<T> {
  return { ...prev, loading: true, error: null };
}

const emptyPanels = (): MarketIntelPanelsState => ({
  ingestion: idlePanel(),
  normalization: idlePanel(),
  scoring: idlePanel(),
  signals: idlePanel(),
  opportunities: idlePanel(),
  coupling: idlePanel(),
});

/** Owner dashboard loader: only GET `/api/v1/market/*` (P39-07 envelopes). No ops routes. */
export function useMarketIntelligencePanels(ownerUserId: number | undefined): {
  panels: MarketIntelPanelsState;
  reloadPanel: (layer: MarketIntelLayerKey) => Promise<void>;
  snapshotChainIssues: string[];
} {
  const [panels, setPanels] = useState<MarketIntelPanelsState>(emptyPanels);

  useEffect(() => {
    if (!ownerUserId) {
      setPanels(emptyPanels());
    }
  }, [ownerUserId]);

  const loadIngestion = useCallback(async () => {
    if (!ownerUserId) return;
    const uid = ownerUserId;
    await dedupedFlight(`p39mi:${uid}:ingestion`, async () => {
      setPanels((p) => ({ ...p, ingestion: loadingPanel(p.ingestion) }));
      try {
        const envelope = await fetchMarketV1Envelope<MarketAcquisitionIngestionBatchListResponse>(
          "/market-ingestion/batches?limit=25&offset=0",
        );
        setPanels((p) => ({
          ...p,
          ingestion: { loading: false, error: null, data: envelope.data, meta: envelope.meta },
        }));
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : "Unable to load market ingestion summary.";
        setPanels((p) => ({
          ...p,
          ingestion: { ...p.ingestion, loading: false, error: msg },
        }));
      }
    });
  }, [ownerUserId]);

  const loadNormalization = useCallback(async () => {
    if (!ownerUserId) return;
    const uid = ownerUserId;
    await dedupedFlight(`p39mi:${uid}:normalization`, async () => {
      setPanels((p) => ({ ...p, normalization: loadingPanel(p.normalization) }));
      try {
        const envelope = await fetchMarketV1Envelope<MarketNormalizationRunListResponse>(
          "/market-normalization/runs?limit=50&offset=0",
        );
        setPanels((p) => ({
          ...p,
          normalization: { loading: false, error: null, data: envelope.data, meta: envelope.meta },
        }));
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : "Unable to load market normalization summary.";
        setPanels((p) => ({
          ...p,
          normalization: { ...p.normalization, loading: false, error: msg },
        }));
      }
    });
  }, [ownerUserId]);

  const loadScoring = useCallback(async () => {
    if (!ownerUserId) return;
    const uid = ownerUserId;
    await dedupedFlight(`p39mi:${uid}:scoring`, async () => {
      setPanels((p) => ({ ...p, scoring: loadingPanel(p.scoring) }));
      try {
        const envelope = await fetchMarketV1Envelope<MarketAcquisitionScoreSnapshotListResponse>(
          "/market-scoring/snapshots?limit=1&offset=0",
        );
        setPanels((p) => ({
          ...p,
          scoring: { loading: false, error: null, data: envelope.data, meta: envelope.meta },
        }));
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : "Unable to load market scoring summary.";
        setPanels((p) => ({
          ...p,
          scoring: { ...p.scoring, loading: false, error: msg },
        }));
      }
    });
  }, [ownerUserId]);

  const loadSignals = useCallback(async () => {
    if (!ownerUserId) return;
    const uid = ownerUserId;
    await dedupedFlight(`p39mi:${uid}:signals`, async () => {
      setPanels((p) => ({ ...p, signals: loadingPanel(p.signals) }));
      try {
        const envelope = await fetchMarketV1Envelope<MarketAcquisitionSignalSnapshotListResponse>(
          "/market-signal-snapshots?limit=1&offset=0",
        );
        setPanels((p) => ({
          ...p,
          signals: { loading: false, error: null, data: envelope.data, meta: envelope.meta },
        }));
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : "Unable to load market signal summary.";
        setPanels((p) => ({
          ...p,
          signals: { ...p.signals, loading: false, error: msg },
        }));
      }
    });
  }, [ownerUserId]);

  const loadOpportunities = useCallback(async () => {
    if (!ownerUserId) return;
    const uid = ownerUserId;
    await dedupedFlight(`p39mi:${uid}:opportunities`, async () => {
      setPanels((p) => ({ ...p, opportunities: loadingPanel(p.opportunities) }));
      try {
        const envelope = await fetchMarketV1Envelope<MarketAcquisitionOpportunitySnapshotListResponse>(
          "/market-opportunities/snapshots?limit=1&offset=0",
        );
        setPanels((p) => ({
          ...p,
          opportunities: { loading: false, error: null, data: envelope.data, meta: envelope.meta },
        }));
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : "Unable to load market opportunity summary.";
        setPanels((p) => ({
          ...p,
          opportunities: { ...p.opportunities, loading: false, error: msg },
        }));
      }
    });
  }, [ownerUserId]);

  const loadCoupling = useCallback(async () => {
    if (!ownerUserId) return;
    const uid = ownerUserId;
    await dedupedFlight(`p39mi:${uid}:coupling`, async () => {
      setPanels((p) => ({ ...p, coupling: loadingPanel(p.coupling) }));
      try {
        const envelope = await fetchMarketV1Envelope<PortfolioMarketCouplingSnapshotListResponse>(
          "/market-portfolio-coupling/snapshots?limit=1&offset=0",
        );
        setPanels((p) => ({
          ...p,
          coupling: { loading: false, error: null, data: envelope.data, meta: envelope.meta },
        }));
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : "Unable to load portfolio-market coupling summary.";
        setPanels((p) => ({
          ...p,
          coupling: { ...p.coupling, loading: false, error: msg },
        }));
      }
    });
  }, [ownerUserId]);

  useEffect(() => {
    if (!ownerUserId) {
      return;
    }
    setPanels((prev) => ({
      ingestion: loadingPanel(prev.ingestion),
      normalization: loadingPanel(prev.normalization),
      scoring: loadingPanel(prev.scoring),
      signals: loadingPanel(prev.signals),
      opportunities: loadingPanel(prev.opportunities),
      coupling: loadingPanel(prev.coupling),
    }));

    void loadIngestion();
    queueMicrotask(() => {
      void loadNormalization();
    });
    queueMicrotask(() => {
      void loadScoring();
      void loadSignals();
    });
    queueMicrotask(() => {
      void loadOpportunities();
      void loadCoupling();
    });
  }, [ownerUserId, loadIngestion, loadNormalization, loadScoring, loadSignals, loadOpportunities, loadCoupling]);

  const reloadPanel = useCallback(
    async (layer: MarketIntelLayerKey) => {
      switch (layer) {
        case "ingestion":
          await loadIngestion();
          break;
        case "normalization":
          await loadNormalization();
          break;
        case "scoring":
          await loadScoring();
          break;
        case "signals":
          await loadSignals();
          break;
        case "opportunities":
          await loadOpportunities();
          break;
        case "coupling":
          await loadCoupling();
          break;
        default:
          break;
      }
    },
    [loadCoupling, loadIngestion, loadNormalization, loadOpportunities, loadScoring, loadSignals],
  );

  const snapshotChainIssues = useMemo(() => {
    return buildMarketSnapshotChainIssues({
      score: panels.scoring.data?.items[0] ?? null,
      signal: panels.signals.data?.items[0] ?? null,
      opportunity: panels.opportunities.data?.items[0] ?? null,
      coupling: panels.coupling.data?.items[0] ?? null,
    });
  }, [panels.coupling.data, panels.opportunities.data, panels.scoring.data, panels.signals.data]);

  return { panels, reloadPanel, snapshotChainIssues };
}
