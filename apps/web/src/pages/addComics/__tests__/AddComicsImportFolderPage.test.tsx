import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as photoImport from "../../../api/photoImport";
import { AddComicsImportFolderPage } from "../AddComicsImportFolderPage";

vi.mock("../../../components/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const folderSession: photoImport.PhotoImportSession = {
  id: 1,
  session_token: "folder-tok",
  status: "active",
  created_at: "2026-06-19T00:00:00Z",
  expires_at: "2026-06-20T00:00:00Z",
  last_seen_at: null,
  source_device: "folder_import",
  confirmed_count: 0,
  uploaded_photo_count: 3,
  detected_book_count: 0,
  capture_mode: "single_comic",
  mobile_url: "http://localhost/photo-import/mobile/folder-tok",
  desktop_review_url: "http://localhost/add-comics/photo/session/folder-tok",
};

const emptyQueue: photoImport.PhotoImportFolderQueueStatus = {
  pending_uploads: 0,
  processing: 0,
  processed: 3,
  failed: 0,
  vision_reads: 3,
  pending_inventory: 0,
  queue_empty: true,
};

beforeEach(() => {
  cleanup();
  vi.restoreAllMocks();
  localStorage.clear();
  vi.spyOn(photoImport, "createPhotoImportSession").mockResolvedValue(folderSession);
  vi.spyOn(photoImport, "getPhotoImportSession").mockResolvedValue(folderSession);
  vi.spyOn(photoImport, "getPhotoImportFolderQueue").mockResolvedValue(emptyQueue);
  vi.spyOn(photoImport, "processPhotoImportFolderPending").mockResolvedValue({
    started_image_ids: [],
    queue: emptyQueue,
  });
  vi.spyOn(photoImport, "qrCodeUrlForLink").mockReturnValue("data:image/png;base64,xx");
  vi.spyOn(photoImport, "mobilePhotoImportUrl").mockReturnValue("http://localhost/mobile");
});

describe("AddComicsImportFolderPage", () => {
  it("starts a folder session and shows QR plus queue stats", async () => {
    render(
      <MemoryRouter>
        <AddComicsImportFolderPage />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: /Start import folder session/i }));
    await waitFor(() => {
      expect(screen.getByAltText(/QR code/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Background processing/i)).toBeInTheDocument();
    expect(screen.getByText(/Queue empty/i)).toBeInTheDocument();
    expect(localStorage.getItem("comicos.importFolder.sessionToken")).toBe("folder-tok");
  });
});

describe("photoImportReviewPath", () => {
  it("builds exceptions review URL for folder import", () => {
    expect(
      photoImport.photoImportReviewPath("folder-tok", { exceptionsOnly: true, fromFolder: true }),
    ).toBe("/add-comics/photo/session/folder-tok?exceptions=1&from=folder");
  });
});
