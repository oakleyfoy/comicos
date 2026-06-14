import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient, type ReceivingSessionItemRead } from "../../../api/client";
import { RecognitionReviewModal } from "../RecognitionReviewModal";

function buildItem(overrides: Partial<ReceivingSessionItemRead> = {}): ReceivingSessionItemRead {
  return {
    id: 10,
    receiving_session_id: 1,
    sequence_index: 0,
    recognition_bucket: "REVIEW",
    status: "REVIEW",
    recognition_confidence: 0.88,
    recognition_snapshot_json: {
      series: "Venom",
      issue_number: "7",
      publisher: "Marvel",
      catalog_issue_id: 700,
      winning_source: "catalog_image_fingerprint",
      cover_image_url: "https://example.com/venom-7.jpg",
    },
    candidate_snapshot_json: [],
    selected_candidate_index: null,
    selected_candidate_json: null,
    user_corrected: false,
    uploaded_at: "2026-06-14T00:00:00Z",
    created_at: "2026-06-14T00:00:00Z",
    updated_at: "2026-06-14T00:00:00Z",
    ...overrides,
  } as ReceivingSessionItemRead;
}

function sessionWith(item: ReceivingSessionItemRead) {
  return {
    id: 1,
    status: "ACTIVE",
    total_items: 1,
    verified_items: 0,
    review_items: 1,
    unknown_items: 0,
    confirmed_items: 0,
    skipped_items: 0,
    created_at: "2026-06-14T00:00:00Z",
    updated_at: "2026-06-14T00:00:00Z",
    items: [item],
  } as never;
}

beforeEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("RecognitionReviewModal", () => {
  it("shows the matched issue and plain-language confidence", () => {
    render(
      <RecognitionReviewModal
        open
        sessionId={1}
        item={buildItem()}
        onSessionUpdate={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByTestId("review-matched-title")).toHaveTextContent("Venom #7");
    expect(screen.getByText("ComicOS is not fully sure.")).toBeInTheDocument();
    expect(screen.getByText("Matched by cover image.")).toBeInTheDocument();
    expect(screen.getByTestId("review-debug-row")).toHaveTextContent("catalog_image_fingerprint");
  });

  it("accepts the current match via the confirm API", async () => {
    const item = buildItem();
    const onClose = vi.fn();
    const onSessionUpdate = vi.fn();
    vi.spyOn(apiClient, "confirmReceivingSessionItem").mockResolvedValue({
      session: sessionWith({ ...item, status: "CONFIRMED" }),
      item: { ...item, status: "CONFIRMED" },
    });

    render(
      <RecognitionReviewModal
        open
        sessionId={1}
        item={item}
        onSessionUpdate={onSessionUpdate}
        onClose={onClose}
      />,
    );

    await act(async () => {
      fireEvent.click(screen.getByTestId("review-accept-match"));
    });

    expect(apiClient.confirmReceivingSessionItem).toHaveBeenCalledWith(1, expect.objectContaining({ item_id: 10, decision: "confirm" }));
    expect(onSessionUpdate).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalledWith("accept");
  });

  it("shows nearby candidates and corrects via the correction API", async () => {
    const item = buildItem();
    const correctedItem = buildItem({
      user_corrected: true,
      corrected_catalog_issue_id: 100,
      selected_candidate_index: 1,
      corrected_recognition_snapshot_json: {
        series: "Venom",
        issue_number: "1",
        publisher: "Marvel",
        catalog_issue_id: 100,
        winning_source: "user_correction",
      },
    });
    vi.spyOn(apiClient, "listRecognitionCatalogCandidates").mockResolvedValue([
      { catalog_issue_id: 100, series: "Venom", issue_number: "1", publisher: "Marvel", confidence: 0, source: "catalog_nearby" },
      { catalog_issue_id: 107, series: "Venom", issue_number: "7", publisher: "Marvel", confidence: 1, source: "catalog_nearby" },
    ]);
    const correctSpy = vi.spyOn(apiClient, "correctReceivingSessionItem").mockResolvedValue({
      session: sessionWith(correctedItem),
      item: correctedItem,
    });

    render(
      <RecognitionReviewModal
        open
        sessionId={1}
        item={item}
        onSessionUpdate={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    await act(async () => {
      fireEvent.click(screen.getByTestId("review-choose-different"));
    });
    await waitFor(() => expect(screen.getByTestId("candidate-card-100")).toBeInTheDocument());

    await act(async () => {
      fireEvent.click(screen.getByTestId("candidate-card-100"));
    });
    expect(screen.getByTestId("review-preview-selection")).toHaveTextContent("Venom #1");

    await act(async () => {
      fireEvent.click(screen.getByTestId("review-confirm-selected"));
    });

    expect(correctSpy).toHaveBeenCalledWith(1, 10, expect.objectContaining({ catalog_issue_id: 100 }));
    // Back to summary showing the corrected issue
    await waitFor(() => expect(screen.getByTestId("review-matched-title")).toHaveTextContent("Venom #1"));
  });

  it("searches the catalog and returns results", async () => {
    vi.spyOn(apiClient, "listRecognitionCatalogCandidates").mockResolvedValue([
      { catalog_issue_id: 100, series: "Venom", issue_number: "1", publisher: "Marvel", confidence: 0.9, source: "catalog_search" },
    ]);

    render(
      <RecognitionReviewModal
        open
        sessionId={1}
        item={buildItem({ recognition_snapshot_json: {} })}
        onSessionUpdate={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    // No match -> Search Catalog is available
    await act(async () => {
      fireEvent.click(screen.getByTestId("review-search-catalog"));
    });
    fireEvent.change(screen.getByTestId("catalog-search-input"), { target: { value: "Venom 1 Marvel" } });
    await act(async () => {
      fireEvent.click(screen.getByTestId("catalog-search-submit"));
    });

    await waitFor(() => expect(screen.getByTestId("candidate-card-100")).toBeInTheDocument());
  });

  it("cancels without confirming", async () => {
    const onClose = vi.fn();
    render(
      <RecognitionReviewModal
        open
        sessionId={1}
        item={buildItem()}
        onSessionUpdate={vi.fn()}
        onClose={onClose}
      />,
    );

    await act(async () => {
      fireEvent.click(screen.getByTestId("review-cancel"));
    });
    expect(onClose).toHaveBeenCalledWith("cancel");
  });
});
