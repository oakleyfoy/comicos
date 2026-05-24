import type { CollectionHistoricalTimelineEventRow } from "../api/client";

export function describeHistoricalTimelineEvent(ev: CollectionHistoricalTimelineEventRow): string {
  const k = ev.event_type;
  switch (k) {
    case "inventory_added":
      return "Inventory copy created";
    case "preorder_created":
      return "Preorder line recorded";
    case "release_day":
      return "Street / release calendar date stored";
    case "expected_ship_window":
      return "Expected ship date stored";
    case "inventory_received":
      return "Marked received";
    case "scan_completed":
      return "Cover scan processed";
    case "ocr_completed":
      return ev.evidence_json?.replay_item_kind === "ocr_replay_item"
        ? "OCR replay completed"
        : "OCR processed";
    case "ocr_failed":
      return "OCR failed";
    case "relationship_reviewed":
      return ev.evidence_json?.replay_item_kind === "relationship_replay_item"
        ? "Relationship pipeline replay recorded"
        : "Link decision recorded";
    case "canonical_suggestion_reviewed":
      return "Canonical suggestion reviewed";
    case "conflict_detected":
      return "Conflict opened";
    case "conflict_resolved":
      return "Conflict moved out of open state";
    case "duplicate_detected":
      return "Duplicate group review seeded";
    case "variant_family_detected":
      return "Probable variant family signal captured";
    default:
      return k;
  }
}

export function timelineDotClass(ev: CollectionHistoricalTimelineEventRow): string {
  if (ev.event_type === "inventory_received") {
    return "bg-emerald-400/70";
  }
  if (
    ev.event_type === "ocr_failed"
    || ev.event_type === "conflict_detected"
  ) {
    return "bg-rose-400/70";
  }
  return "bg-cyan-400/60";
}
