import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as photoImport from "../../../api/photoImport";
import { PhotoImportMobilePage } from "../PhotoImportMobilePage";

const sessionMock = {
  id: 1,
  session_token: "tok",
  status: "active",
  created_at: "2026-06-17T00:00:00Z",
  expires_at: "2026-06-18T00:00:00Z",
  last_seen_at: null,
  source_device: null,
  confirmed_count: 0,
  uploaded_photo_count: 0,
  detected_book_count: 0,
  mobile_url: "http://localhost/photo-import/mobile/tok",
  desktop_review_url: "http://localhost/add-comics/photo/session/tok",
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/photo-import/mobile/test-token-123"]}>
      <Routes>
        <Route path="/photo-import/mobile/:token" element={<PhotoImportMobilePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.spyOn(photoImport, "heartbeatPhotoImportSession").mockResolvedValue(sessionMock);
  vi.spyOn(photoImport, "getPhotoImportSession").mockResolvedValue(sessionMock);
  vi.spyOn(photoImport, "uploadPhotoImportImages").mockResolvedValue([]);
});

describe("PhotoImportMobilePage", () => {
  it("renders separate Take Photo and Upload From Photos actions", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "Add Comics From Your Phone" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Take Photo" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload From Photos" })).toBeInTheDocument();
    expect(
      screen.getByText(/Use Upload From Photos for camera roll, screenshots, or pictures you took earlier./i),
    ).toBeInTheDocument();
  });

  it("uses capture on camera input only", () => {
    renderPage();
    const camera = screen.getByTestId("photo-import-camera-input");
    const gallery = screen.getByTestId("photo-import-gallery-input");
    expect(camera).toHaveAttribute("capture", "environment");
    expect(camera).toHaveAttribute("accept", "image/*");
    expect(gallery).toHaveAttribute("accept", "image/*");
    expect(gallery.hasAttribute("capture")).toBe(false);
    expect(gallery).toHaveAttribute("multiple");
  });

  it("invokes upload handler when gallery files are selected", async () => {
    renderPage();
    const gallery = screen.getByTestId("photo-import-gallery-input") as HTMLInputElement;
    const file = new File(["pixels"], "roll.jpg", { type: "image/jpeg" });
    fireEvent.change(gallery, { target: { files: [file] } });
    await waitFor(() => {
      expect(photoImport.uploadPhotoImportImages).toHaveBeenCalledWith("test-token-123", [file]);
    });
  });
});
