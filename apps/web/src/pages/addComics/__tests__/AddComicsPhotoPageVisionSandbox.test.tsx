import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as photoImport from "../../../api/photoImport";
import { AddComicsPhotoPage } from "../AddComicsPhotoPage";

const navigate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigate };
});

vi.mock("../../../components/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const sandboxSession: photoImport.PhotoImportSession = {
  id: 1,
  session_token: "sandbox-tok",
  status: "active",
  created_at: "2026-06-19T00:00:00Z",
  expires_at: "2026-06-20T00:00:00Z",
  last_seen_at: null,
  source_device: "desktop",
  confirmed_count: 0,
  uploaded_photo_count: 2,
  detected_book_count: 2,
  capture_mode: "single_comic",
  mobile_url: "http://localhost/photo-import/mobile/sandbox-tok",
  desktop_review_url: "http://localhost/add-comics/photo/sandbox/session/sandbox-tok",
  vision_sandbox: true,
};

beforeEach(() => {
  cleanup();
  vi.restoreAllMocks();
  navigate.mockReset();
  vi.spyOn(photoImport, "createPhotoImportSession").mockResolvedValue(sandboxSession);
  vi.spyOn(photoImport, "getPhotoImportSession").mockResolvedValue(sandboxSession);
  vi.spyOn(photoImport, "qrCodeUrlForLink").mockReturnValue("data:image/png;base64,xx");
  vi.spyOn(photoImport, "mobilePhotoImportUrl").mockReturnValue("http://localhost/mobile");
});

describe("AddComicsPhotoPage vision sandbox", () => {
  it("links to sandbox review route when flag is on", async () => {
    render(
      <MemoryRouter>
        <AddComicsPhotoPage />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: /Start Phone Photo Session/i }));
    await waitFor(() => {
      expect(screen.getByText(/GPT reads complete/i)).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /Review GPT vision reads/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Review GPT vision reads/i }));
    expect(navigate).toHaveBeenCalledWith("/add-comics/photo/sandbox/session/sandbox-tok");
  });
});
