import type { AiDraftOrderItem } from "../api/client";
import {
  CREATOR_METADATA_WARNING_FRAGMENT,
  RELEASE_DATE_METADATA_WARNING_FRAGMENT,
} from "../api/client";

export type MetadataReviewSeverity = "LOW" | "MEDIUM" | "HIGH";

export type CreatorRoleId = "writers" | "artists" | "cover_artists";

export const CREATOR_ROLE_LABELS: Record<CreatorRoleId, string> = {
  writers: "Writers",
  artists: "Artists",
  cover_artists: "Cover artists",
};

export type MetadataReviewSummary = {
  issue: string;
  severity: MetadataReviewSeverity;
  comic: string;
  affectedField: string;
  detectedValue: string;
  canonicalValue: string;
  recommendedAction: string;
  noCorrectionNecessary: boolean;
  humanizedNotes: string[];
};

const SEVERITY_RANK: Record<MetadataReviewSeverity, number> = {
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
};

export function metadataReviewSeverityClass(severity: MetadataReviewSeverity): string {
  switch (severity) {
    case "HIGH":
      return "border-rose-400/40 bg-rose-500/15 text-rose-100 ring-rose-400/30";
    case "MEDIUM":
      return "border-amber-400/35 bg-amber-500/15 text-amber-100 ring-amber-400/30";
    case "LOW":
    default:
      return "border-slate-400/30 bg-slate-500/15 text-slate-100 ring-slate-400/25";
  }
}

export function displayMetadataValue(value: string | null | undefined): string {
  const trimmed = value?.trim();
  return trimmed ? trimmed : "Not provided";
}

function joinList(values: string[] | null | undefined): string {
  if (!values?.length) {
    return "";
  }
  return values.map((v) => (v ?? "").trim()).filter(Boolean).join(", ");
}

export function zipCreatorSlots(
  item: AiDraftOrderItem,
  role: CreatorRoleId,
): Array<{ slot: number; raw: string; canonical: string }> {
  const rawMap = {
    writers: item.raw_writers,
    artists: item.raw_artists,
    cover_artists: item.raw_cover_artists,
  } as const;
  const canonMap = {
    writers: item.canonical_writers,
    artists: item.canonical_artists,
    cover_artists: item.canonical_cover_artists,
  } as const;
  const displayMap = {
    writers: item.writers,
    artists: item.artists,
    cover_artists: item.cover_artists,
  } as const;

  const fb = displayMap[role] ?? [];
  const rawSource = rawMap[role];
  const canonSource = canonMap[role];

  const rawVals =
    rawSource !== undefined && rawSource !== null && rawSource.length > 0
      ? rawSource.map((segment) => (segment ?? "").trim())
      : fb.map((segment) => (segment ?? "").trim());

  const canonVals =
    canonSource !== undefined && canonSource !== null && canonSource.length > 0
      ? canonSource.map((segment) => (segment ?? "").trim())
      : fb.map((segment) => (segment ?? "").trim());

  const count = Math.max(rawVals.length, canonVals.length);
  const pairs: Array<{ slot: number; raw: string; canonical: string }> = [];
  for (let slot = 0; slot < count; slot += 1) {
    const raw = rawVals[slot] ?? "";
    const canonical = canonVals[slot] ?? raw;
    if (!raw.trim() && !canonical.trim()) {
      continue;
    }
    pairs.push({ slot, raw, canonical });
  }
  return pairs;
}

export function formatCreatorBullets(rows: Array<{ raw: string; canonical: string }>): string {
  if (!rows.length) {
    return "Not provided";
  }
  return rows.map(({ raw, canonical }) => `${raw} → ${canonical}`).join("; ");
}

export function creatorAliasRowKey(
  itemLineIndex: number,
  role: CreatorRoleId,
  slot: number,
): string {
  return `${itemLineIndex}|${role}|${slot}`;
}

export function severityForMetadataReviewNote(note: string): MetadataReviewSeverity {
  if (note.includes(RELEASE_DATE_METADATA_WARNING_FRAGMENT)) {
    return "HIGH";
  }
  if (
    note.includes("Variant description appears malformed") ||
    note.includes("Issue number included multiple formatting") ||
    note.includes("Review canonical publisher")
  ) {
    return "MEDIUM";
  }
  if (
    note.includes(CREATOR_METADATA_WARNING_FRAGMENT) ||
    note.includes("list format was malformed or unsupported")
  ) {
    return "LOW";
  }
  if (note.includes("low confidence")) {
    return "LOW";
  }
  return "LOW";
}

export function humanizeMetadataReviewNote(note: string): string {
  if (
    note.includes(CREATOR_METADATA_WARNING_FRAGMENT) ||
    note.includes("list format was malformed or unsupported")
  ) {
    const roleMatch = note.match(/^(\w+(?:\s+\w+)?)\s+list format/i);
    const roleLabel = roleMatch ? roleMatch[1].toLowerCase() : "creator";
    return `ComicOS preserved the ${roleLabel} information but could not fully normalize it automatically.`;
  }
  if (note.includes(RELEASE_DATE_METADATA_WARNING_FRAGMENT)) {
    return "ComicOS preserved the release date but could not fully normalize it automatically.";
  }
  if (note.includes("Variant description appears malformed")) {
    return "ComicOS preserved the variant description but could not fully normalize it automatically.";
  }
  if (note.includes("Issue number included multiple formatting")) {
    return "ComicOS preserved the issue number but could not fully normalize every formatting marker.";
  }
  if (note.includes("Review canonical publisher")) {
    return "ComicOS could not confidently match this publisher name to a canonical label.";
  }
  return note;
}

function affectedFieldFromNote(note: string): string {
  if (/^Writer list format/i.test(note)) {
    return "Writers";
  }
  if (/^Cover artist list format/i.test(note)) {
    return "Cover artists";
  }
  if (/^Artist list format/i.test(note)) {
    return "Artists";
  }
  if (note.includes(RELEASE_DATE_METADATA_WARNING_FRAGMENT)) {
    return "Release date";
  }
  if (note.includes("Review canonical publisher")) {
    return "Publisher";
  }
  if (note.includes("canonical issue")) {
    return "Issue number";
  }
  if (note.includes("Variant description")) {
    return "Variant";
  }
  if (note.includes("canonical series") || note.includes("title")) {
    return "Title";
  }
  return "Metadata";
}

function fieldPairForAffectedField(
  item: AiDraftOrderItem,
  affectedField: string,
): { detected: string; canonical: string } {
  switch (affectedField) {
    case "Writers":
      return {
        detected: joinList(item.raw_writers ?? item.writers),
        canonical: joinList(item.canonical_writers ?? item.writers),
      };
    case "Artists":
      return {
        detected: joinList(item.raw_artists ?? item.artists),
        canonical: joinList(item.canonical_artists ?? item.artists),
      };
    case "Cover artists":
      return {
        detected: joinList(item.raw_cover_artists ?? (item.cover_artist ? [item.cover_artist] : [])),
        canonical: joinList(item.canonical_cover_artists ?? item.cover_artists),
      };
    case "Release date":
      return {
        detected: displayMetadataValue(item.raw_release_date ?? item.release_date),
        canonical: displayMetadataValue(item.parsed_release_date ?? item.release_date),
      };
    case "Publisher":
      return {
        detected: displayMetadataValue(item.raw_publisher),
        canonical: displayMetadataValue(item.canonical_publisher ?? item.publisher),
      };
    case "Issue number":
      return {
        detected: displayMetadataValue(item.raw_issue_number ?? item.issue_number),
        canonical: displayMetadataValue(item.canonical_issue_number ?? item.issue_number),
      };
    case "Variant":
      return {
        detected: displayMetadataValue(item.raw_variant_text),
        canonical: displayMetadataValue(item.canonical_variant_text),
      };
    case "Title":
      return {
        detected: displayMetadataValue(item.raw_title ?? item.title),
        canonical: displayMetadataValue(item.canonical_title ?? item.title),
      };
    default:
      return { detected: "—", canonical: "—" };
  }
}

function normalizeCompareValue(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, " ");
}

export function valuesEquivalentForReview(detected: string, canonical: string): boolean {
  const d = normalizeCompareValue(detected);
  const c = normalizeCompareValue(canonical);
  if (!d && !c) {
    return true;
  }
  if (d === "not provided" && c === "not provided") {
    return true;
  }
  return d === c && d.length > 0;
}

function recommendedActionFor(
  severity: MetadataReviewSeverity,
  affectedField: string,
  noCorrectionNecessary: boolean,
): string {
  if (noCorrectionNecessary) {
    return "Confirm the preserved value looks correct, then choose Looks Good.";
  }
  if (affectedField === "Publisher") {
    return "Create a publisher alias or edit the canonical publisher before confirming.";
  }
  if (affectedField === "Writers" || affectedField === "Artists" || affectedField === "Cover artists") {
    return "Confirm names look correct, or create a creator alias for future imports.";
  }
  if (affectedField === "Release date") {
    return "Verify the release date in the draft item before confirming the order.";
  }
  if (severity === "HIGH") {
    return "Review the affected field in the draft item before confirming.";
  }
  return "Review the summary above, then confirm or adjust the draft item.";
}

export function buildMetadataReviewSummary(item: AiDraftOrderItem): MetadataReviewSummary {
  const notes = item.metadata_review_notes ?? [];
  const humanizedNotes = notes.map(humanizeMetadataReviewNote);
  const primaryNote =
    notes.length === 0
      ? ""
      : [...notes].sort(
          (a, b) =>
            SEVERITY_RANK[severityForMetadataReviewNote(b)] -
            SEVERITY_RANK[severityForMetadataReviewNote(a)],
        )[0];

  const affectedField = primaryNote ? affectedFieldFromNote(primaryNote) : "Metadata";
  const { detected, canonical } = fieldPairForAffectedField(item, affectedField);
  const noCorrectionNecessary = valuesEquivalentForReview(detected, canonical);
  const severity = primaryNote ? severityForMetadataReviewNote(primaryNote) : "LOW";
  const issue = primaryNote
    ? humanizeMetadataReviewNote(primaryNote)
    : "This item was flagged for metadata review.";

  const comicTitle = displayMetadataValue(item.canonical_title ?? item.title);
  const comicIssue = displayMetadataValue(item.canonical_issue_number ?? item.issue_number);
  const comic = `${comicTitle} #${comicIssue}`;

  return {
    issue,
    severity,
    comic,
    affectedField,
    detectedValue: detected || "—",
    canonicalValue: canonical || "—",
    recommendedAction: recommendedActionFor(severity, affectedField, noCorrectionNecessary),
    noCorrectionNecessary,
    humanizedNotes,
  };
}

export function hasMalformedReleaseDateNote(item: AiDraftOrderItem): boolean {
  return (
    item.metadata_review_notes?.some((note) =>
      note.includes(RELEASE_DATE_METADATA_WARNING_FRAGMENT),
    ) ?? false
  );
}

export function hasCreatorMetadataWarningNotes(item: AiDraftOrderItem): boolean {
  return (
    item.metadata_review_notes?.some((note) =>
      note.includes(CREATOR_METADATA_WARNING_FRAGMENT),
    ) ?? false
  );
}
