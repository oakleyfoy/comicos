import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as intake from "../../../api/intake";
import { IntakeFullCoverCapturePage } from "../IntakeFullCoverCapturePage";

function renderCapture(token = "tok-1", itemId = "42") {
  return render(
    <MemoryRouter initialEntries={[`/intake/full-cover/${token}/${itemId}`]}>
      <Routes>
        <Route
          path="/intake/full-cover/:token/:itemId"
          element={<IntakeFullCoverCapturePage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("IntakeFullCoverCapturePage", () => {
  it("captures and uploads to the token endpoint, then confirms", async () => {
    const uploadSpy = vi
      .spyOn(intake, "uploadIntakeFullCoverPhotoByToken")
      .mockResolvedValue({ id: 42 } as intake.IntakeItem);
    renderCapture();
    fireEvent.click(screen.getByTestId("full-cover-capture-open-camera"));
    const input = screen.getByTestId("full-cover-capture-input") as HTMLInputElement;
    const file = new File(["jpeg"], "cover.jpg", { type: "image/jpeg" });
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() => expect(uploadSpy).toHaveBeenCalledWith("tok-1", 42, file));
    expect(await screen.findByText(/Sent\./)).toBeInTheDocument();
  });

  it("surfaces upload errors", async () => {
    vi.spyOn(intake, "uploadIntakeFullCoverPhotoByToken").mockRejectedValue(
      new Error("Image too small"),
    );
    renderCapture();
    fireEvent.click(screen.getByTestId("full-cover-capture-open-camera"));
    const input = screen.getByTestId("full-cover-capture-input") as HTMLInputElement;
    const file = new File(["jpeg"], "cover.jpg", { type: "image/jpeg" });
    fireEvent.change(input, { target: { files: [file] } });
    expect(await screen.findByText("Image too small")).toBeInTheDocument();
  });
});
