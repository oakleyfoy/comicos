import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as intake from "../../../api/intake";
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

const intakeSession: intake.IntakeSession = {
  id: 1,
  session_token: "intake-tok",
  name: null,
  status: "active",
  source_device: "desktop",
  scanned_count: 0,
  created_at: "2026-06-24T00:00:00Z",
  expires_at: "2026-06-25T00:00:00Z",
  last_seen_at: null,
  scanner_url: "http://localhost/intake/scan/intake-tok",
  review_url: "http://localhost/intake/review/intake-tok",
};

beforeEach(() => {
  cleanup();
  vi.restoreAllMocks();
  navigate.mockReset();
  vi.spyOn(intake, "createIntakeSession").mockResolvedValue(intakeSession);
  vi.spyOn(intake, "getIntakeSession").mockResolvedValue(intakeSession);
  vi.spyOn(photoImport, "qrCodeUrlForLink").mockReturnValue("data:image/png;base64,xx");
});

describe("AddComicsPhotoPage hands-free intake", () => {
  it("starts an intake session and opens the intake review screen", async () => {
    render(
      <MemoryRouter>
        <AddComicsPhotoPage />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: /Start Intake Session/i }));
    await waitFor(() => {
      expect(intake.createIntakeSession).toHaveBeenCalled();
    });
    expect(screen.getByRole("button", { name: /Open review screen/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Open review screen/i }));
    expect(navigate).toHaveBeenCalledWith("/intake/review/intake-tok");
  });
});
