import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as photoImport from "../../../api/photoImport";
import { PhotoImportReviewPage } from "../PhotoImportReviewPage";

vi.mock("../../../components/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

function makeRead(overrides: Partial<photoImport.PhotoImportVisionRead> = {}): photoImport.PhotoImportVisionRead {
  return {
    id: 10,
    session_id: 1,
    image_id: 5,
    detection_index: 0,
    publisher: "Marvel",
    series: "Falcon",
    issue_number: "1",
    issue_title: "Take Flight",
    variant_description: null,
    year: "2017",
    cover_date: null,
    barcode: "75960608751700111",
    confidence: 0.95,
    reasoning: "Cover logo matches Falcon #1.",
    possible_alternates: ["The Falcon (2017)"],
    raw_response: null,
    is_correct: null,
    feedback_notes: null,
    added_to_inventory: false,
    catalog_issue_id: null,
    catalog_variant_id: null,
    catalog_cover_url: null,
    match_method: null,
    match_confidence: null,
    catalog_series: null,
    catalog_issue_number: null,
    catalog_publisher: null,
    catalog_alternates: [],
    created_at: "2026-06-20T00:00:00Z",
    ...overrides,
  };
}

const SESSION: photoImport.PhotoImportSession = {
  id: 1,
  session_token: "tok",
  status: "review_ready",
  created_at: "2026-06-20T00:00:00Z",
  expires_at: "2026-06-21T00:00:00Z",
  last_seen_at: null,
  source_device: "desktop",
  confirmed_count: 0,
  uploaded_photo_count: 1,
  detected_book_count: 1,
  capture_mode: "single_comic",
  mobile_url: "http://localhost/mobile",
  desktop_review_url: "http://localhost/review",
  vision_sandbox: true,
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/add-comics/photo/session/tok"]}>
      <Routes>
        <Route path="/add-comics/photo/session/:token" element={<PhotoImportReviewPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.spyOn(photoImport, "listSessionVisionReads").mockResolvedValue([makeRead()]);
  vi.spyOn(photoImport, "getPhotoImportSession").mockResolvedValue(SESSION);
  vi.spyOn(photoImport, "originalImageUrl").mockReturnValue("http://localhost/img");
});

describe("PhotoImportReviewPage", () => {
  it("shows GPT identification fields and reasoning", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByDisplayValue("Falcon")).toBeInTheDocument());
    expect(screen.getByDisplayValue("Marvel")).toBeInTheDocument();
    expect(screen.getByText(/Cover logo matches Falcon #1/)).toBeInTheDocument();
    expect(screen.getByText(/GPT confidence 95%/)).toBeInTheDocument();
  });

  it("renders one card per detected book in a multi-book photo", async () => {
    vi.spyOn(photoImport, "listSessionVisionReads").mockResolvedValue([
      makeRead({ id: 10, detection_index: 0, series: "Falcon", issue_number: "1" }),
      makeRead({ id: 11, detection_index: 1, series: "Hawkeye", issue_number: "2" }),
    ]);
    vi.spyOn(photoImport, "getPhotoImportSession").mockResolvedValue({ ...SESSION, detected_book_count: 2 });
    renderPage();
    await waitFor(() => expect(screen.getByDisplayValue("Falcon")).toBeInTheDocument());
    expect(screen.getByDisplayValue("Hawkeye")).toBeInTheDocument();
    expect(screen.getByText(/Photo 1 — 2 books found/i)).toBeInTheDocument();
  });

  it("adds a book to inventory", async () => {
    const update = vi.spyOn(photoImport, "updateVisionRead").mockResolvedValue(makeRead());
    const add = vi.spyOn(photoImport, "addVisionReadToInventory").mockResolvedValue({
      vision_read: makeRead({ added_to_inventory: true }),
      acquisition_id: null,
      created_count: 1,
      inventory_copy_ids: [42],
    });
    renderPage();
    await waitFor(() => expect(screen.getByDisplayValue("Falcon")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /^Add to inventory$/i }));
    await waitFor(() => expect(add).toHaveBeenCalledWith(10));
    expect(update).toHaveBeenCalled();
    expect(await screen.findByText(/Added to your collection \(1 copy\)/i)).toBeInTheDocument();
  });

  it("adds all books in the session", async () => {
    const addAll = vi.spyOn(photoImport, "addAllSessionReads").mockResolvedValue({
      added_count: 1,
      total_copies: 1,
      results: [],
    });
    renderPage();
    await waitFor(() => expect(screen.getByDisplayValue("Falcon")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /Add all to collection/i }));
    await waitFor(() => expect(addAll).toHaveBeenCalledWith("tok"));
    expect(await screen.findByText(/Added 1 book/i)).toBeInTheDocument();
  });

  it("re-reads the photo and rebuilds its books", async () => {
    const reread = vi
      .spyOn(photoImport, "rereadVisionRead")
      .mockResolvedValue([makeRead({ id: 99, series: "Batman", issue_number: "404" })]);
    renderPage();
    await waitFor(() => expect(screen.getByDisplayValue("Falcon")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /Re-read with GPT/i }));
    await waitFor(() => expect(reread).toHaveBeenCalledWith(10));
    expect(await screen.findByDisplayValue("Batman")).toBeInTheDocument();
  });

  it("switches to an alternate catalog match", async () => {
    vi.spyOn(photoImport, "listSessionVisionReads").mockResolvedValue([
      makeRead({
        catalog_issue_id: 500,
        catalog_series: "Falcon",
        catalog_issue_number: "1",
        match_method: "text",
        catalog_alternates: [
          { catalog_issue_id: 777, series: "The Falcon", issue_number: "1", publisher: "Marvel", cover_url: null, confidence: 0.6 },
        ],
      }),
    ]);
    const choose = vi
      .spyOn(photoImport, "chooseVisionReadMatch")
      .mockResolvedValue(makeRead({ catalog_issue_id: 777, catalog_series: "The Falcon", catalog_issue_number: "1" }));
    renderPage();
    await waitFor(() => expect(screen.getByDisplayValue("Falcon")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /The Falcon #1/i }));
    await waitFor(() => expect(choose).toHaveBeenCalledWith(10, 777));
  });

  it("records feedback", async () => {
    const feedback = vi
      .spyOn(photoImport, "submitVisionReadFeedback")
      .mockResolvedValue(makeRead({ is_correct: true }));
    renderPage();
    await waitFor(() => expect(screen.getByDisplayValue("Falcon")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /✓ Correct/i }));
    await waitFor(() => expect(feedback).toHaveBeenCalled());
    expect(await screen.findByText(/GPT got this right/i)).toBeInTheDocument();
  });
});
