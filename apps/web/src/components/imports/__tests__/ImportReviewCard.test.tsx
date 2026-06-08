import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { ImportReviewCard } from "../ImportReviewCard";

afterEach(() => {
  cleanup();
});

function buildItem(overrides: Record<string, unknown> = {}) {
  return {
    publisher: "Image",
    title: "Terminal",
    releaseDate: "2026-07-22",
    releaseStatus: "not_released_yet" as const,
    orderStatus: "preordered" as const,
    issueNumber: "1",
    coverName: "Cover B Variant Ryan Ottley Cover",
    printing: "",
    ratio: "",
    variantType: "",
    coverArtist: "Ryan Ottley",
    quantity: "1",
    rawItemPrice: "4.99",
    catalogReleaseSourceText: "Verified release date from catalog",
    coverImageUrl: undefined,
    coverThumbnailUrl: undefined,
    hasCoverImage: false,
    ...overrides,
  };
}

function Harness({
  imageUrl,
}: {
  imageUrl?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const [item, setItem] = useState(buildItem({ coverThumbnailUrl: imageUrl, coverImageUrl: imageUrl }));

  return (
    <ImportReviewCard
      item={item}
      isExpanded={expanded}
      canRemove={true}
      isSubmitting={false}
      itemError={{}}
      lifecycleBadge={{
        label: "Upcoming Release",
        detail: "Releases Jul 22, 2026 · 44 days remaining",
        className: "border-cyan-400/30 bg-cyan-500/10 text-cyan-100",
      }}
      cardSurfaceClassName="border-cyan-400/35 bg-cyan-950/40"
      onToggleDetails={() => setExpanded((current) => !current)}
      onRemove={() => undefined}
      onUpdate={(field, value) => setItem((current) => ({ ...current, [field]: value }))}
      clearItemError={() => undefined}
      canScanCover={false}
      scanCoverBusy={false}
      onScanCoverSelected={() => undefined}
    />
  );
}

describe("ImportReviewCard", () => {
  it("renders compact card title, issue, and status", () => {
    render(<Harness />);
    expect(screen.getByText("Terminal #1")).toBeInTheDocument();
    expect(screen.getByText("July 22, 2026")).toBeInTheDocument();
    expect(screen.getByText("Upcoming Release")).toBeInTheDocument();
    expect(screen.getByText("Verified release date from catalog")).toBeInTheDocument();
  });

  it("renders placeholder when no image exists", () => {
    render(<Harness />);
    expect(screen.getByText("NO COVER")).toBeInTheDocument();
  });

  it("renders image when a cover url exists", () => {
    render(<Harness imageUrl="https://example.com/terminal-thumb.jpg" />);
    expect(screen.getByRole("img", { name: "Terminal #1" })).toHaveAttribute(
      "src",
      "https://example.com/terminal-thumb.jpg",
    );
  });

  it("reveals editable fields after clicking Show Details", () => {
    render(<Harness />);
    expect(screen.queryByDisplayValue("2026-07-22")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show Details" }));
    expect(screen.getByText("Release Date")).toBeInTheDocument();
    expect(screen.getByDisplayValue("2026-07-22")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Image")).toBeInTheDocument();
  });

  it("keeps advanced fields hidden in the collapsed state", () => {
    render(<Harness />);
    expect(screen.queryByText("Optional. Exact dates are preserved when provided; year-only values stay year-only.")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Variant Type")).not.toBeInTheDocument();
  });
});
