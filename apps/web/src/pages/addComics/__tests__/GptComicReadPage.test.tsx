import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GptComicReadPage } from "../GptComicReadPage";

const readComicWithGpt = vi.fn();

vi.mock("../../../api/gptComicRead", () => ({
  readComicWithGpt: (...args: unknown[]) => readComicWithGpt(...args),
  GptComicReadApiError: class extends Error {},
}));

vi.mock("../../../components/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <GptComicReadPage />
    </MemoryRouter>,
  );
}

const result = {
  publisher: "Marvel",
  series: "Falcon",
  issue_number: "1",
  issue_title: "Take Flight",
  year: "2017",
  cover_date: "December 2017",
  variant_description: "",
  barcode: "",
  confidence: 0.92,
  reasoning: "Cover logo and trade dress match The Falcon #1.",
  possible_alternates: ["The Falcon (2017)"],
  raw_response: {},
  model: "gpt-4o",
  image_width: 400,
  image_height: 600,
};

beforeEach(() => {
  cleanup();
  readComicWithGpt.mockReset();
  readComicWithGpt.mockResolvedValue(result);
  if (!URL.createObjectURL) {
    Object.defineProperty(URL, "createObjectURL", { value: () => "blob:preview", configurable: true });
    Object.defineProperty(URL, "revokeObjectURL", { value: () => undefined, configurable: true });
  }
});

describe("GptComicReadPage", () => {
  it("renders the upload UI", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "GPT Comic Read" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Upload image/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Read with GPT/i })).toBeInTheDocument();
  });

  it("shows a preview after selecting an image", async () => {
    renderPage();
    const input = screen.getByTestId("gpt-comic-read-input") as HTMLInputElement;
    const file = new File(["pixels"], "falcon.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() => {
      expect(screen.getByAltText("Uploaded comic preview")).toBeInTheDocument();
    });
  });

  it("calls the endpoint and displays GPT fields", async () => {
    renderPage();
    const input = screen.getByTestId("gpt-comic-read-input") as HTMLInputElement;
    const file = new File(["pixels"], "falcon.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /Read with GPT/i }));
    await waitFor(() => {
      expect(readComicWithGpt).toHaveBeenCalledWith(file);
    });
    expect(await screen.findByText("Marvel")).toBeInTheDocument();
    expect(screen.getByText("Falcon")).toBeInTheDocument();
    expect(screen.getByText("Take Flight")).toBeInTheDocument();
    expect(screen.getByText(/trade dress match/)).toBeInTheDocument();
    expect(screen.getByText("The Falcon (2017)")).toBeInTheDocument();
  });

  it("does not render catalog/candidate/confirm UI", async () => {
    renderPage();
    const input = screen.getByTestId("gpt-comic-read-input") as HTMLInputElement;
    const file = new File(["pixels"], "falcon.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /Read with GPT/i }));
    await screen.findByText("Marvel");
    expect(screen.queryByText(/Suggested matches/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Catalog cover/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Catalog verified/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/candidate/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Confirm/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Reject/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/Select correct issue/i)).not.toBeInTheDocument();
  });
});
