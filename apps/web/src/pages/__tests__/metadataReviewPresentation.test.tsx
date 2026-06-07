import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AiDraftOrderItem } from "../api/client";
import { MetadataReviewDraftCard } from "../../components/MetadataReviewDraftCard";
import {
  buildMetadataReviewSummary,
  humanizeMetadataReviewNote,
  severityForMetadataReviewNote,
  valuesEquivalentForReview,
} from "../metadataReviewPresentation";

function creatorWarningItem(overrides: Partial<AiDraftOrderItem> = {}): AiDraftOrderItem {
  return {
    publisher: "Marvel",
    title: "Spider-Man",
    issue_number: "1",
    canonical_title: "Spider-Man",
    canonical_issue_number: "1",
    raw_cover_artists: ["John Romita Jr."],
    canonical_cover_artists: ["John Romita Jr."],
    metadata_review_required: true,
    metadata_review_notes: [
      "Cover artist list format was malformed or unsupported. Review preserved creator values.",
    ],
    quantity: 1,
    raw_item_price: "3.99",
    cover_name: null,
    printing: null,
    ratio: null,
    variant_type: null,
    cover_artist: null,
    ...overrides,
  };
}

describe("metadataReviewPresentation", () => {
  it("humanizes creator malformed notes for plain language", () => {
    const note =
      "Cover artist list format was malformed or unsupported. Review preserved creator values.";
    expect(humanizeMetadataReviewNote(note)).toBe(
      "ComicOS preserved the cover artist information but could not fully normalize it automatically.",
    );
    expect(severityForMetadataReviewNote(note)).toBe("LOW");
  });

  it("builds review summary with severity, field, and no-correction hint when values match", () => {
    const summary = buildMetadataReviewSummary(creatorWarningItem());
    expect(summary.severity).toBe("LOW");
    expect(summary.affectedField).toBe("Cover artists");
    expect(summary.detectedValue).toBe("John Romita Jr.");
    expect(summary.noCorrectionNecessary).toBe(true);
    expect(summary.issue).toContain("could not fully normalize it automatically");
    expect(valuesEquivalentForReview("A", "A")).toBe(true);
  });

  it("maps release date warnings to HIGH severity", () => {
    const note = "Release date format was malformed or unsupported. Review preserved release chronology.";
    expect(severityForMetadataReviewNote(note)).toBe("HIGH");
    expect(humanizeMetadataReviewNote(note)).toContain("release date");
  });
});

describe("MetadataReviewDraftCard", () => {
  afterEach(() => {
    cleanup();
  });

  it("surfaces Review Required summary before advanced panels", () => {
    render(
      <MemoryRouter>
        <MetadataReviewDraftCard
          index={0}
          item={creatorWarningItem()}
          onLooksGood={vi.fn()}
          onCreateAlias={vi.fn()}
          onIgnoreWarning={vi.fn()}
        />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("metadata-review-required-card")).toBeInTheDocument();
    expect(screen.getByText("Review Required")).toBeInTheDocument();
    expect(screen.getByTestId("metadata-review-severity")).toHaveTextContent("LOW");
    expect(screen.getByTestId("metadata-review-no-correction")).toHaveTextContent(
      "No correction appears necessary.",
    );
    expect(screen.queryByText("Raw Parsed Metadata")).not.toBeVisible();
    expect(screen.getByRole("button", { name: "Looks Good" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create Alias" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ignore Warning" })).toBeInTheDocument();
    expect(
      screen.queryByText(/list format was malformed or unsupported/i),
    ).not.toBeInTheDocument();
  });

  it("reveals technical metadata inside Advanced Details", () => {
    render(
      <MemoryRouter>
        <MetadataReviewDraftCard
          index={0}
          item={creatorWarningItem()}
          onLooksGood={vi.fn()}
          onCreateAlias={vi.fn()}
          onIgnoreWarning={vi.fn()}
        />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByText("Advanced Details"));
    expect(screen.getByText("Raw Parsed Metadata")).toBeVisible();
    expect(screen.getByText("Canonical Metadata")).toBeVisible();
    expect(screen.getByText("Creator Slots")).toBeVisible();
    expect(screen.getByText("Metadata Identity Key")).toBeVisible();
  });
});
