import { describe, expect, it } from "vitest";

import type { AiDraftOrderItem } from "../api/client";
import {
  buildMissingPublisherQuestion,
  buildPendingImportMetadataQuestions,
  buildPrimaryMetadataQuestion,
} from "../importMetadataQuestions";

function item(overrides: Partial<AiDraftOrderItem> = {}): AiDraftOrderItem {
  return {
    title: "Jeff The Land Shark Superstar",
    issue_number: "1",
    quantity: 1,
    raw_item_price: "3.99",
    ...overrides,
  };
}

describe("importMetadataQuestions", () => {
  it("asks for publisher when parse note says publisher missing", () => {
    const question = buildPrimaryMetadataQuestion(
      item({
        metadata_review_required: true,
        metadata_review_notes: ["Publisher missing after parse."],
      }),
      10,
    );
    expect(question?.kind).toBe("missing_publisher");
    expect(question?.prompt).toMatch(/publisher/i);
    expect(question?.comicLabel).toContain("Jeff");
  });

  it("uses confirm flow when normalization already matches", () => {
    const question = buildPrimaryMetadataQuestion(
      item({
        metadata_review_required: true,
        metadata_review_notes: [
          "Cover artist list format was malformed or unsupported. Review preserved creator values.",
        ],
        raw_cover_artists: ["John Romita Jr."],
        canonical_cover_artists: ["John Romita Jr."],
      }),
      0,
    );
    expect(question?.kind).toBe("confirm_parsed");
  });

  it("queues missing publisher lines without metadata flags", () => {
    const draft = { items: [item({ publisher: "" })] };
    const questions = buildPendingImportMetadataQuestions(draft, [""]);
    expect(questions).toHaveLength(1);
    expect(questions[0].kind).toBe("missing_publisher");
  });

  it("does not duplicate publisher question when metadata flag already covers it", () => {
    const draft = {
      items: [
        item({
          metadata_review_required: true,
          metadata_review_notes: ["Publisher missing after parse."],
        }),
      ],
    };
    const questions = buildPendingImportMetadataQuestions(draft, [""]);
    expect(questions).toHaveLength(1);
    expect(buildMissingPublisherQuestion(item(), 0).kind).toBe("missing_publisher");
  });
});
