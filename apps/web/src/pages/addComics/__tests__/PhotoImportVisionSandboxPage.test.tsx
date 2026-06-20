import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PhotoImportVisionSandboxPage } from "../PhotoImportVisionSandboxPage";

const listSessionVisionReads = vi.fn();
const submitVisionReadFeedback = vi.fn();

vi.mock("../../../components/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("../../../api/photoImport", () => ({
  listSessionVisionReads: (...args: unknown[]) => listSessionVisionReads(...args),
  submitVisionReadFeedback: (...args: unknown[]) => submitVisionReadFeedback(...args),
  originalImageUrl: (token: string, imageId: number) =>
    `http://test/original/${token}/${imageId}`,
}));

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/add-comics/photo/sandbox/session/tok-sandbox"]}>
      <Routes>
        <Route path="/add-comics/photo/sandbox/session/:token" element={<PhotoImportVisionSandboxPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("PhotoImportVisionSandboxPage", () => {
  beforeEach(() => {
    listSessionVisionReads.mockResolvedValue([
      {
        id: 1,
        session_id: 10,
        image_id: 99,
        publisher: "Vertigo",
        series: "Preacher",
        issue_number: "58",
        issue_title: null,
        variant_description: null,
        year: "1999",
        cover_date: null,
        barcode: null,
        confidence: 0.94,
        reasoning: "Recognized Preacher trade dress.",
        possible_alternates: ["Preacher Annual"],
        raw_response: { parsed: {} },
        is_correct: null,
        feedback_notes: null,
        created_at: "2026-06-19T12:00:00Z",
      },
    ]);
    submitVisionReadFeedback.mockResolvedValue({
      id: 1,
      is_correct: true,
      feedback_notes: "good",
    });
  });

  it("renders GPT fields without catalog match UI", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Preacher")).toBeInTheDocument();
    });
    expect(screen.getByText("GPT vision read")).toBeInTheDocument();
    expect(screen.getByText(/Recognized Preacher trade dress/)).toBeInTheDocument();
    expect(screen.getByText("Preacher Annual")).toBeInTheDocument();
    expect(screen.queryByText(/Suggested matches/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Catalog cover/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/fingerprint/i)).not.toBeInTheDocument();
  });

  it("feedback buttons call API", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("Preacher")).toBeInTheDocument());
    const buttons = screen.getAllByRole("button", { name: /GPT got this right/i });
    fireEvent.click(buttons[0]!);
    expect(submitVisionReadFeedback).toHaveBeenCalledWith(1, expect.objectContaining({ is_correct: true }));
  });
});
