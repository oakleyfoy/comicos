import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as intake from "../../../api/intake";
import { IntakeReviewPage } from "../IntakeReviewPage";

vi.mock("qrcode", () => ({
  // Plain function so vi.restoreAllMocks() can't wipe the resolved value.
  default: { toDataURL: () => Promise.resolve("data:image/png;base64,qr") },
}));

function stubCoarsePointer(coarse: boolean) {
  vi.stubGlobal(
    "matchMedia",
    (query: string) =>
      ({
        matches: coarse,
        media: query,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
        addListener: () => undefined,
        removeListener: () => undefined,
        onchange: null,
        dispatchEvent: () => false,
      }) as unknown as MediaQueryList,
  );
}

function renderReview() {
  return render(
    <MemoryRouter initialEntries={["/intake/review/tok-1"]}>
      <Routes>
        <Route path="/intake/review/:token" element={<IntakeReviewPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

const baseReview = {
  session: {
    id: 1,
    session_token: "tok-1",
    name: null,
    status: "active",
    source_device: null,
    scanned_count: 3,
    created_at: "2026-06-24T00:00:00Z",
    expires_at: "2026-06-25T00:00:00Z",
    last_seen_at: null,
    scanner_url: "/intake/scan/tok-1",
    review_url: "/intake/review/tok-1",
  },
  counts: {
    scanned: 3,
    queued: 1,
    processing: 0,
    auto_matched: 1,
    ready_for_review: 1,
    needs_review: 0,
    needs_full_cover_photo: 0,
    added_to_inventory: 0,
    rejected: 0,
    failed: 0,
  },
  items: [
    {
      id: 11,
      session_id: 1,
      status: "ready_for_review",
      confidence: 0.8,
      match_source: "comicvine",
      raw_barcode: "76194134192703921",
      normalized_barcode: "76194134192703921",
      base_upc: "761941341927",
      extension: "03921",
      selected_catalog_issue_id: 500,
      selected_variant_id: null,
      matched_publisher: "DC Comics",
      matched_series: "Superman",
      matched_issue_number: "39",
      matched_year: "2015",
      cover_url: null,
      reason: null,
      error: null,
      image_url: "/api/v1/intake/sessions/tok-1/items/11/image",
      acquisition_id: null,
      inventory_copy_id: null,
      created_at: "2026-06-24T00:00:00Z",
      processed_at: "2026-06-24T00:01:00Z",
      candidates: [],
    },
  ],
};

beforeEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("IntakeReviewPage", () => {
  it("shows live counts and item details", async () => {
    vi.spyOn(intake, "getIntakeReview").mockResolvedValue(baseReview);
    renderReview();
    expect(await screen.findByTestId("count-auto_matched")).toHaveTextContent("1");
    expect(screen.getByTestId("count-ready_for_review")).toHaveTextContent("1");
    expect(screen.getByText("Superman #39")).toBeInTheDocument();
    expect(screen.getByText("DC Comics · 2015")).toBeInTheDocument();
  });

  it("shows local catalog success for high-confidence barcode match", async () => {
    vi.spyOn(intake, "getIntakeReview").mockResolvedValue({
      ...baseReview,
      items: [
        {
          ...baseReview.items[0],
          status: "auto_matched",
          match_source: "catalog_upc",
          reason: "Printed supplement OCR read issue #19, but barcode matched Superman #39.",
        },
      ],
    });
    renderReview();
    expect(await screen.findByText("Barcode verified against local catalog.")).toBeInTheDocument();
    expect(screen.getByText(/Printed supplement OCR read issue #19/)).toBeInTheDocument();
    expect(screen.queryByText(/Barcode and printed supplement disagree/)).not.toBeInTheDocument();
  });

  it("adds an item to inventory", async () => {
    vi.spyOn(intake, "getIntakeReview").mockResolvedValue(baseReview);
    const addSpy = vi.spyOn(intake, "addIntakeItemToInventory").mockResolvedValue({
      ...baseReview.items[0],
      status: "added_to_inventory",
      inventory_copy_id: 99,
    });
    renderReview();
    const addButton = await screen.findByRole("button", { name: "Add to inventory" });
    fireEvent.click(addButton);
    await waitFor(() => expect(addSpy).toHaveBeenCalledWith(11));
  });

  const cvOnlyReview = {
    ...baseReview,
    items: [{ ...baseReview.items[0], selected_catalog_issue_id: null }],
  };

  it("imports and accepts a ComicVine-only candidate", async () => {
    vi.spyOn(intake, "getIntakeReview").mockResolvedValue(cvOnlyReview);
    const importSpy = vi.spyOn(intake, "importAndAcceptIntakeItem").mockResolvedValue({
      ...cvOnlyReview.items[0],
      status: "auto_matched",
      selected_catalog_issue_id: 777,
    });
    renderReview();
    const btn = await screen.findByRole("button", { name: /Import & Accept/ });
    fireEvent.click(btn);
    await waitFor(() => expect(importSpy).toHaveBeenCalledWith(11));
  });

  it("chooses a different issue via catalog search", async () => {
    vi.spyOn(intake, "getIntakeReview").mockResolvedValue(cvOnlyReview);
    vi.spyOn(intake, "searchCatalogIssues").mockResolvedValue({
      results: [
        {
          catalog_issue_id: 900,
          series: "Superman",
          issue_number: "39",
          publisher: "DC Comics",
          cover_url: null,
        },
      ],
    });
    const chooseSpy = vi.spyOn(intake, "chooseIntakeItemIssue").mockResolvedValue({
      ...cvOnlyReview.items[0],
      status: "auto_matched",
      selected_catalog_issue_id: 900,
    });
    renderReview();
    fireEvent.click(await screen.findByRole("button", { name: "Choose different issue" }));
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    fireEvent.click(await screen.findByRole("button", { name: /Superman #39 DC Comics/ }));
    await waitFor(() => expect(chooseSpy).toHaveBeenCalledWith(11, 900));
  });

  it("shows full-cover prompt and camera/upload actions", async () => {
    vi.spyOn(intake, "getIntakeReview").mockResolvedValue({
      ...baseReview,
      counts: { ...baseReview.counts, needs_full_cover_photo: 1 },
      items: [
        {
          ...baseReview.items[0],
          id: 42,
          status: "needs_full_cover_photo",
          barcode_read: { needs_full_cover_photo: true },
          candidates: [],
        },
      ],
    });
    renderReview();
    expect(await screen.findByTestId("full-cover-prompt-42")).toBeInTheDocument();
    expect(screen.getByTestId("full-cover-camera-42")).toHaveTextContent("Take Full Cover Photo");
    expect(screen.getByTestId("full-cover-upload-42")).toHaveTextContent("Upload Existing Photo");
    expect(screen.getByTestId("full-cover-prompt-42")).toHaveTextContent(
      "Take a full front-cover photo to identify by cover art.",
    );
    const cameraInput = screen.getByTestId("full-cover-camera-input");
    expect(cameraInput).toHaveAttribute("accept", "image/*");
    expect(cameraInput).toHaveAttribute("capture", "environment");
    expect(screen.getByTestId("full-cover-upload-input")).toHaveAttribute("accept", "image/*");
  });

  it("renders a frontend build marker for deployment verification", async () => {
    vi.spyOn(intake, "getIntakeReview").mockResolvedValue(baseReview);
    renderReview();
    const marker = await screen.findByTestId("frontend-build-marker");
    expect(marker).toHaveTextContent(/build /);
  });

  it("hides fingerprint candidates and Import & Accept in needs_full_cover_photo state", async () => {
    vi.spyOn(intake, "getIntakeReview").mockResolvedValue({
      ...baseReview,
      counts: { ...baseReview.counts, needs_full_cover_photo: 1 },
      items: [
        {
          ...baseReview.items[0],
          id: 42,
          status: "needs_full_cover_photo",
          selected_catalog_issue_id: null,
          barcode_read: {
            needs_full_cover_photo: true,
            barcode_gap: {
              needs_review_top_candidates: [
                { series: "Silver Surfer", issue_number: "84", publisher: "Marvel", confidence: 0.7 },
              ],
            },
          },
          candidates: [
            {
              id: 1,
              catalog_issue_id: 1000,
              variant_id: null,
              publisher: "Marvel",
              series: "Silver Surfer",
              issue_number: "84",
              cover_url: null,
              score: 70,
              source: "fingerprint",
              rank: 0,
            },
          ],
        },
      ],
    });
    renderReview();
    expect(await screen.findByTestId("full-cover-camera-42")).toBeInTheDocument();
    expect(screen.queryByText(/Silver Surfer/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Import & Accept/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Rescan" })).toBeInTheDocument();
  });

  const fullCoverReview = {
    ...baseReview,
    counts: { ...baseReview.counts, needs_full_cover_photo: 1 },
    items: [
      {
        ...baseReview.items[0],
        id: 42,
        status: "needs_full_cover_photo",
        barcode_read: { needs_full_cover_photo: true },
        candidates: [],
      },
    ],
  };

  it("uploads captured full-cover photo directly on a phone (camera device)", async () => {
    stubCoarsePointer(true); // phone/tablet: capture happens right here
    const uploadSpy = vi.spyOn(intake, "uploadIntakeFullCoverPhoto").mockResolvedValue({
      ...baseReview.items[0],
      id: 42,
      status: "processing",
    });
    vi.spyOn(intake, "getIntakeReview").mockResolvedValue(fullCoverReview);
    renderReview();
    fireEvent.click(await screen.findByTestId("full-cover-camera-42"));
    const input = screen.getByTestId("full-cover-camera-input") as HTMLInputElement;
    const file = new File(["jpeg"], "cover.jpg", { type: "image/jpeg" });
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() => expect(uploadSpy).toHaveBeenCalledWith(42, file));
  });

  it("surfaces facsimile/reprint candidates first with a non-authoritative-barcode note", async () => {
    vi.spyOn(intake, "getIntakeReview").mockResolvedValue({
      ...baseReview,
      counts: { ...baseReview.counts, needs_review: 1 },
      items: [
        {
          ...baseReview.items[0],
          id: 55,
          status: "needs_review",
          selected_catalog_issue_id: null,
          matched_series: null,
          matched_issue_number: null,
          barcode_read: {
            barcode_gap: {
              facsimile_reprint_detected: true,
              needs_review_top_candidates: [
                {
                  series: "Amazing Spider-Man",
                  issue_number: "122",
                  publisher: "Marvel",
                  confidence: 0,
                  source: "gcd_facsimile",
                  is_facsimile_reprint: true,
                },
              ],
            },
          },
          candidates: [],
        },
      ],
    });
    renderReview();
    expect(await screen.findByTestId("facsimile-note-55")).toHaveTextContent(
      /isn.t authoritative/i,
    );
    const list = screen.getByTestId("fp-candidates-55");
    expect(list).toHaveTextContent("Amazing Spider-Man #122");
    expect(list).toHaveTextContent("Facsimile / reprint");
  });

  it("hands off to the phone via QR on a desktop (no camera)", async () => {
    stubCoarsePointer(false); // desktop: cannot reach a camera, must hand off
    vi.spyOn(intake, "getIntakeReview").mockResolvedValue(fullCoverReview);
    renderReview();
    fireEvent.click(await screen.findByTestId("full-cover-camera-42"));
    const modal = await screen.findByTestId("full-cover-handoff-modal");
    expect(modal).toBeInTheDocument();
    expect(await screen.findByTestId("full-cover-handoff-qr")).toBeInTheDocument();
    expect(
      screen.getByText(/\/intake\/full-cover\/tok-1\/42$/),
    ).toBeInTheDocument();
  });
});
