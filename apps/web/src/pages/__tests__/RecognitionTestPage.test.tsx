import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { RecognitionTestPage } from "../RecognitionTestPage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div data-testid="app-shell">{children}</div>,
}));

vi.mock("../../components/PageHeader", () => ({
  PageHeader: ({ title, description }: { title: string; description: string }) => (
    <header>
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  ),
}));

vi.mock("../../components/StatusBanner", () => ({
  StatusBanner: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

describe("RecognitionTestPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "identifyComicFromImage").mockResolvedValue({
      status: "success",
      bucket: "VERIFIED",
      confidence: 0.992,
      series: "Batman",
      issue_number: "497",
      variant: "Cover A",
      publisher: "DC",
      release_date: "1993-07-01",
      cover_image_url: "https://example.com/batman-497.jpg",
      candidate_count: 2,
      candidates: [
        {
          series: "Batman",
          issue_number: "497",
          variant: "Cover A",
          publisher: "DC",
          release_date: "1993-07-01",
          confidence: 0.992,
          cover_image_url: "https://example.com/batman-497.jpg",
          source: "ExternalCatalogIssue",
          source_id: 1,
        },
        {
          series: "Batman",
          issue_number: "498",
          variant: "Cover A",
          publisher: "DC",
          release_date: "1993-08-01",
          confidence: 0.731,
          cover_image_url: "https://example.com/batman-498.jpg",
          source: "ExternalCatalogIssue",
          source_id: 2,
        },
      ],
      metrics: {
        recognition_attempts: 1,
        verified_results: 1,
        review_results: 0,
        unknown_results: 0,
        average_confidence: 0.992,
      },
    });
  });

  it("uploads an image and renders the recognition result", async () => {
    render(
      <MemoryRouter>
        <RecognitionTestPage />
      </MemoryRouter>,
    );

    const input = screen.getByLabelText("Select files") as HTMLInputElement;
    const file = new File([new Uint8Array([1, 2, 3, 4])], "batman.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [file] } });

    expect(await screen.findByRole("heading", { name: "Recognition Test" })).toBeInTheDocument();
    await waitFor(() => {
      const identifiedBook = screen.getByRole("heading", { name: "Identified book" }).closest("section");
      expect(identifiedBook).not.toBeNull();
      if (identifiedBook) {
        expect(identifiedBook).toHaveTextContent("Batman #497");
        expect(identifiedBook).toHaveTextContent("VERIFIED");
      }
    });
  });
});

