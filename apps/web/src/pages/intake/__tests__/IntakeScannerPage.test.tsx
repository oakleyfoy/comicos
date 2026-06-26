import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as intake from "../../../api/intake";
import { IntakeScannerPage } from "../IntakeScannerPage";

const session = {
  id: 1,
  session_token: "tok-1",
  name: null,
  status: "active",
  source_device: null,
  scanned_count: 0,
  acquisition_id: 2,
  acquisition_label: "Test batch",
  created_at: "2026-06-24T00:00:00Z",
  expires_at: "2026-06-25T00:00:00Z",
  last_seen_at: null,
  scanner_url: "/intake/scan/tok-1",
  review_url: "/intake/review/tok-1",
};

function renderScanner(initialEntry = "/intake/scan/tok-1") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/intake/scan/:token" element={<IntakeScannerPage />} />
        <Route path="/intake/scan" element={<IntakeScannerPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.spyOn(intake, "getIntakeSession").mockResolvedValue(session);
  vi.spyOn(intake, "setIntakeSessionStatus").mockResolvedValue(session);
});

describe("IntakeScannerPage", () => {
  it("starts scanning with a desktop-linked token and is capture-only", async () => {
    renderScanner();
    await waitFor(() => expect(intake.getIntakeSession).toHaveBeenCalledWith("tok-1"));
    fireEvent.click(screen.getByRole("button", { name: "Start session" }));

    expect(await screen.findByTestId("intake-file-input")).toBeInTheDocument();
    expect(screen.queryByText(/Book identified/i)).not.toBeInTheDocument();
    expect(screen.getByTestId("scanned-count")).toHaveTextContent("0");
  });

  it("increments scanned count immediately on capture (non-blocking)", async () => {
    const enqueue = vi
      .spyOn(intake, "enqueueIntakeItem")
      .mockResolvedValue({ item_id: 9, status: "queued", scanned_count: 1 });

    renderScanner();
    await waitFor(() => expect(intake.getIntakeSession).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: "Start session" }));
    const input = await screen.findByTestId("intake-file-input");
    fireEvent.change(input, { target: { files: [new File(["x"], "scan.jpg", { type: "image/jpeg" })] } });

    await waitFor(() => expect(enqueue).toHaveBeenCalledWith("tok-1", expect.any(File), undefined));
    expect(screen.getByTestId("scanned-count")).toHaveTextContent("1");
  });

  it("requires a QR-linked session when opened without a token", async () => {
    renderScanner("/intake/scan");
    fireEvent.click(screen.getByRole("button", { name: "Start session" }));
    expect(
      await screen.findByText(/Open this page from the QR link/i),
    ).toBeInTheDocument();
  });
});
