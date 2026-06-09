import type { AiDraftOrderItem } from "../api/client";
import { RELEASE_DATE_METADATA_WARNING_FRAGMENT } from "../api/client";
import {
  buildMetadataReviewSummary,
  humanizeMetadataReviewNote,
  severityForMetadataReviewNote,
  type MetadataReviewSummary,
} from "./metadataReviewPresentation";

export type ImportMetadataQuestionKind =
  | "missing_publisher"
  | "publisher_canonical"
  | "release_date"
  | "confirm_parsed";

export type ImportMetadataQuestion = {
  itemIndex: number;
  kind: ImportMetadataQuestionKind;
  comicLabel: string;
  prompt: string;
  /** Prefilled answer when applicable */
  suggestedAnswer?: string;
  /** Raw value from invoice when confirming publisher spelling */
  rawPublisher?: string;
  severity: "LOW" | "MEDIUM" | "HIGH";
  /** Human label for the field being confirmed (confirm_parsed) */
  affectedField?: string;
  /** Value read from the order / invoice */
  invoiceValue?: string;
  /** Value ComicOS will store and use after enrichment */
  parsedValue?: string;
};

function comicLabelForItem(item: AiDraftOrderItem): string {
  const title = (item.canonical_title ?? item.title ?? "Untitled").trim();
  const issue = (item.canonical_issue_number ?? item.issue_number ?? "").trim();
  return issue ? `${title} #${issue}` : title;
}

function primaryMetadataNote(item: AiDraftOrderItem): string {
  const notes = item.metadata_review_notes ?? [];
  if (!notes.length) {
    return "";
  }
  const ranked = [...notes].sort(
    (a, b) =>
      severityRank(severityForMetadataReviewNote(b)) - severityRank(severityForMetadataReviewNote(a)),
  );
  return ranked[0] ?? "";
}

function severityRank(severity: "LOW" | "MEDIUM" | "HIGH"): number {
  if (severity === "HIGH") {
    return 3;
  }
  if (severity === "MEDIUM") {
    return 2;
  }
  return 1;
}

function displayableReviewValue(value: string): string | undefined {
  const trimmed = value.trim();
  if (!trimmed || trimmed === "—" || trimmed === "Not provided") {
    return undefined;
  }
  return trimmed;
}

function confirmQuestionFieldDetails(
  summary: MetadataReviewSummary,
): Pick<ImportMetadataQuestion, "affectedField" | "invoiceValue" | "parsedValue"> {
  const affectedField =
    summary.affectedField !== "Metadata" ? summary.affectedField : undefined;
  return {
    affectedField,
    invoiceValue: displayableReviewValue(summary.detectedValue),
    parsedValue: displayableReviewValue(summary.canonicalValue),
  };
}

export function buildPrimaryMetadataQuestion(
  item: AiDraftOrderItem,
  itemIndex: number,
): ImportMetadataQuestion | null {
  const note = primaryMetadataNote(item);
  const comicLabel = comicLabelForItem(item);
  const severity = note ? severityForMetadataReviewNote(note) : "LOW";

  if (note.includes("Publisher missing after parse") || note.toLowerCase().includes("publisher missing")) {
    return {
      itemIndex,
      kind: "missing_publisher",
      comicLabel,
      prompt: "We could not read a publisher from your order. Which publisher is this issue from?",
      suggestedAnswer: item.canonical_publisher ?? item.publisher ?? "",
      severity: "MEDIUM",
    };
  }

  if (note.includes("Review canonical publisher")) {
    const raw = (item.raw_publisher ?? "").trim();
    return {
      itemIndex,
      kind: "publisher_canonical",
      comicLabel,
      prompt: raw
        ? `Your invoice shows publisher “${raw}”. What is the correct publisher name for our catalog?`
        : "What is the correct publisher name for this issue?",
      suggestedAnswer: item.canonical_publisher ?? item.publisher ?? raw,
      rawPublisher: raw || undefined,
      severity: "MEDIUM",
    };
  }

  if (note.includes(RELEASE_DATE_METADATA_WARNING_FRAGMENT)) {
    const raw = (item.raw_release_date ?? item.release_date ?? "").trim();
    const parsed = (item.parsed_release_date ?? "").trim();
    return {
      itemIndex,
      kind: "release_date",
      comicLabel,
      prompt: parsed
        ? `Please confirm the release date for this book (we parsed ${parsed}${raw ? ` from “${raw}”` : ""}).`
        : "What is the correct release date for this book?",
      suggestedAnswer: parsed || raw,
      severity: "HIGH",
    };
  }

  const summary = buildMetadataReviewSummary(item);
  const fieldDetails = confirmQuestionFieldDetails(summary);
  if (summary.noCorrectionNecessary) {
    return {
      itemIndex,
      kind: "confirm_parsed",
      comicLabel,
      prompt: summary.issue || humanizeMetadataReviewNote(note),
      severity: summary.severity,
      ...fieldDetails,
    };
  }

  return {
    itemIndex,
    kind: "confirm_parsed",
    comicLabel,
    prompt: note ? humanizeMetadataReviewNote(note) : "Please confirm this line looks correct before we show the full order.",
    suggestedAnswer: summary.canonicalValue !== "—" ? summary.canonicalValue : undefined,
    severity,
    ...fieldDetails,
  };
}

export function buildMissingPublisherQuestion(
  item: AiDraftOrderItem,
  itemIndex: number,
): ImportMetadataQuestion {
  return {
    itemIndex,
    kind: "missing_publisher",
    comicLabel: comicLabelForItem(item),
    prompt: "Which publisher is this issue from?",
    suggestedAnswer: "",
    severity: "MEDIUM",
  };
}

export function buildPendingImportMetadataQuestions(
  draft: { items: AiDraftOrderItem[] } | null,
  formPublishers: string[],
): ImportMetadataQuestion[] {
  if (!draft?.items.length) {
    return [];
  }

  const out: ImportMetadataQuestion[] = [];
  draft.items.forEach((item, index) => {
    if (item.metadata_review_required) {
      const question = buildPrimaryMetadataQuestion(item, index);
      if (question) {
        out.push(question);
      }
      return;
    }
    const publisher = formPublishers[index]?.trim() || item.publisher?.trim() || item.canonical_publisher?.trim();
    if (!publisher) {
      out.push(buildMissingPublisherQuestion(item, index));
    }
  });
  return out;
}
