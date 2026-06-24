import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GptComicReadPage } from "../GptComicReadPage";

const readComicWithGpt = vi.fn();

vi.mock("../../../api/gptComicRead", () => ({
  readComicWithGpt: (...args: unknown[]) => readComicWithGpt(...args),
  GptComicReadApiError: class extends Error {},
  finalMatchSourceLabel: (source: string) =>
    source === "comicvine_barcode" ? "Barcode verified" : source === "catalog" ? "Catalog match" : "GPT only",
  barcodeMethodLabel: (method: string) =>
    method === "local_decode" ? "Local decode" : method === "gpt_barcode_read" ? "GPT barcode crop" : "None",
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

const gptFields = {
  publisher: "DC",
  series: "Superman",
  issue_number: "39",
  issue_title: "",
  year: "2024",
  cover_date: "",
  variant_description: "",
  barcode: "",
  confidence: 0.88,
  reasoning: "Cover reads Superman #39.",
  possible_alternates: [] as string[],
  raw_response: {},
  model: "gpt-4o",
  image_width: 400,
  image_height: 600,
};

const result = {
  gpt_read: gptFields,
  catalog_match: { matched: false, alternates: [] },
  barcode_read: {
    barcode: null,
    barcode_type: null,
    confidence: 0,
    method: "none" as const,
    crop_used: null,
    error: null,
  },
  comicvine_barcode_match: { matched: false, source: "comicvine" },
  final_match_source: "gpt_only" as const,
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
    const file = new File(["pixels"], "superman.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /Read with GPT/i }));
    await waitFor(() => {
      expect(readComicWithGpt).toHaveBeenCalledWith(file);
    });
    expect(await screen.findByText("DC")).toBeInTheDocument();
    expect(screen.getByText("Superman")).toBeInTheDocument();
    expect(screen.getByText(/Cover reads Superman/)).toBeInTheDocument();
  });

  it('renders "Barcode: Not detected" when extraction finds nothing', async () => {
    renderPage();
    const input = screen.getByTestId("gpt-comic-read-input") as HTMLInputElement;
    const file = new File(["pixels"], "superman.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /Read with GPT/i }));
    await screen.findByTestId("gpt-barcode-section");
    expect(screen.getByText("Not detected")).toBeInTheDocument();
    expect(screen.getByText("GPT only")).toBeInTheDocument();
  });

  it("does not render photo-import candidate/confirm UI", async () => {
    renderPage();
    const input = screen.getByTestId("gpt-comic-read-input") as HTMLInputElement;
    const file = new File(["pixels"], "falcon.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /Read with GPT/i }));
    await screen.findByText("Superman");
    expect(screen.queryByText(/Suggested matches/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Confirm/i })).not.toBeInTheDocument();
  });
});
