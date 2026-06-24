import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as intake from "../../../api/intake";
import { IntakeScannerPage } from "../IntakeScannerPage";

function renderScanner() {
  return render(
    <MemoryRouter initialEntries={["/intake/scan"]}>
      <Routes>
        <Route path="/intake/scan" element={<IntakeScannerPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("IntakeScannerPage", () => {
  it("starts a session and is capture-only (no match results shown)", async () => {
    const session = {
      id: 1,
      session_token: "tok-1",
      name: null,
      status: "active",
      source_device: null,
      scanned_count: 0,
      created_at: "2026-06-24T00:00:00Z",
      expires_at: "2026-06-25T00:00:00Z",
      last_seen_at: null,
      scanner_url: "/intake/scan/tok-1",
      review_url: "/intake/review/tok-1",
    };
    vi.spyOn(intake, "createIntakeSession").mockResolvedValue(session);

    renderScanner();
    fireEvent.click(screen.getByRole("button", { name: "Start session" }));

    // jsdom has no camera -> fallback capture input appears; never shows identification.
    expect(await screen.findByTestId("intake-file-input")).toBeInTheDocument();
    expect(screen.queryByText(/Book identified/i)).not.toBeInTheDocument();
    expect(screen.getByTestId("scanned-count")).toHaveTextContent("0");
  });

  it("increments scanned count immediately on capture (non-blocking)", async () => {
    const session = {
      id: 1,
      session_token: "tok-1",
      name: null,
      status: "active",
      source_device: null,
      scanned_count: 0,
      created_at: "2026-06-24T00:00:00Z",
      expires_at: "2026-06-25T00:00:00Z",
      last_seen_at: null,
      scanner_url: "/intake/scan/tok-1",
      review_url: "/intake/review/tok-1",
    };
    vi.spyOn(intake, "createIntakeSession").mockResolvedValue(session);
    const enqueue = vi
      .spyOn(intake, "enqueueIntakeItem")
      .mockResolvedValue({ item_id: 9, status: "queued", scanned_count: 1 });

    renderScanner();
    fireEvent.click(screen.getByRole("button", { name: "Start session" }));
    const input = await screen.findByTestId("intake-file-input");
    fireEvent.change(input, { target: { files: [new File(["x"], "scan.jpg", { type: "image/jpeg" })] } });

    await waitFor(() => expect(enqueue).toHaveBeenCalledWith("tok-1", expect.any(File), undefined));
    expect(screen.getByTestId("scanned-count")).toHaveTextContent("1");
  });
});
