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
    created_at: "2026-06-20T00:00:00Z",
    ...overrides,
  };
}

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

  it("adds the GPT read to inventory", async () => {
    const update = vi.spyOn(photoImport, "updateVisionRead").mockResolvedValue(makeRead());
    const add = vi.spyOn(photoImport, "addVisionReadToInventory").mockResolvedValue({
      vision_read: makeRead({ added_to_inventory: true }),
      acquisition_id: 3,
      created_count: 1,
      inventory_copy_ids: [42],
    });
    renderPage();
    await waitFor(() => expect(screen.getByDisplayValue("Falcon")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /^Add to inventory$/i }));
    await waitFor(() => expect(add).toHaveBeenCalledWith(10));
    expect(update).toHaveBeenCalled();
    expect(await screen.findByText(/Added to inventory \(1 copy\)/i)).toBeInTheDocument();
  });

  it("re-reads the photo with GPT", async () => {
    const reread = vi
      .spyOn(photoImport, "rereadVisionRead")
      .mockResolvedValue(makeRead({ series: "Batman", issue_number: "404" }));
    renderPage();
    await waitFor(() => expect(screen.getByDisplayValue("Falcon")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /Re-read with GPT/i }));
    await waitFor(() => expect(reread).toHaveBeenCalledWith(10));
    expect(await screen.findByDisplayValue("Batman")).toBeInTheDocument();
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

  it("uses an alternate as the series", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByDisplayValue("Falcon")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /The Falcon \(2017\)/i }));
    expect(screen.getByDisplayValue("The Falcon (2017)")).toBeInTheDocument();
  });
});
