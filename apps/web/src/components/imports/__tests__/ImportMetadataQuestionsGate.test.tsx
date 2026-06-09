import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ImportMetadataQuestionsGate } from "../ImportMetadataQuestionsGate";
import type { ImportMetadataQuestion } from "../../../pages/importMetadataQuestions";

afterEach(() => {
  cleanup();
});

const confirmQuestion: ImportMetadataQuestion = {
  itemIndex: 0,
  kind: "confirm_parsed",
  comicLabel: "Corpse Knight #3",
  prompt:
    "ComicOS preserved the cover artist information but could not fully normalize it automatically.",
  severity: "LOW",
  affectedField: "Cover artists",
  invoiceValue: "J. Romita Jr",
  parsedValue: "John Romita Jr.",
};

describe("ImportMetadataQuestionsGate", () => {
  it("shows invoice and ComicOS values for confirm questions", () => {
    render(
      <ImportMetadataQuestionsGate questions={[confirmQuestion]} onAnswer={vi.fn()} />,
    );
    expect(screen.getByText("From your order")).toBeInTheDocument();
    expect(screen.getByText("J. Romita Jr")).toBeInTheDocument();
    expect(screen.getByText("ComicOS will use")).toBeInTheDocument();
    expect(screen.getByText("John Romita Jr.")).toBeInTheDocument();
  });
});
