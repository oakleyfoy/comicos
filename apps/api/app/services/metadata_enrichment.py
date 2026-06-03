import logging
import re
from dataclasses import dataclass
from datetime import date

from sqlmodel import Session

from app.schemas.ai import AiDraftOrderItem, MetadataIdentityComponents, ParseOrderResponse
from app.services.metadata_aliases import (
    STATIC_PUBLISHER_ALIAS_MAP,
    get_active_db_alias_value,
    normalize_alias_lookup_key,
)
from app.services.order_states import (
    default_expected_ship_date,
    default_order_status,
    default_release_status,
)
from app.services.publisher_metadata_autofill import resolve_blank_publisher

LOGGER = logging.getLogger(__name__)

HIGH_CONFIDENCE_TITLE_PUBLISHERS = {
    "DC": ("batman", "superman", "wonder woman"),
    "Marvel": ("spider man", "x men", "avengers"),
    "Image": ("spawn", "invincible"),
}

SOURCE_LINE_PUBLISHER_MARKERS = {
    "DC": re.compile(r"\bdc\b", re.IGNORECASE),
    "Marvel": re.compile(r"\bmarvel\b", re.IGNORECASE),
    "Image": re.compile(r"\bimage\b", re.IGNORECASE),
    "IDW": re.compile(r"\bidw\b", re.IGNORECASE),
    "Mad Cave": re.compile(r"\bmad cave\b", re.IGNORECASE),
}

PUBLISHER_REVIEW_WARNING_PREFIX = "Publisher metadata needs review for items:"
SPECIAL_ISSUE_IDENTIFIERS = {
    "omega": "Omega",
    "alpha": "Alpha",
    "tpb": "TPB",
    "hc": "HC",
}
ISSUE_PREFIX_PATTERN = re.compile(r"^(?:(?:no\.?|issue)\s+)+", re.IGNORECASE)
ISSUE_ANNUAL_PATTERN = re.compile(r"^annual\s+(.+)$", re.IGNORECASE)
NUMERIC_ISSUE_PATTERN = re.compile(r"^0*(\d+)([A-Za-z][A-Za-z0-9]*)?$")
RATIO_SEGMENT_PATTERN = re.compile(r"^1\s*:\s*(\d+)$", re.IGNORECASE)
COVER_PREFIX_PATTERN = re.compile(r"^(?:cover|cvr)\s+([A-Za-z0-9]+)$", re.IGNORECASE)
COVER_SUFFIX_PATTERN = re.compile(r"^([A-Za-z0-9]+)\s+(?:cover|cvr)$", re.IGNORECASE)
ISSUE_FORMAT_REVIEW_NOTE = (
    "Issue number included multiple formatting markers. "
    "Review canonical issue value."
)
ISSUE_LOW_CONFIDENCE_REVIEW_NOTE = (
    "Issue number format was low confidence and preserved conservatively."
)
VARIANT_MALFORMED_REVIEW_NOTE = (
    "Variant description appears malformed or ambiguous. "
    "Review canonical variant value."
)
RELEASE_DATE_PAYLOAD_SEARCH_FRAGMENT = "Release date format was malformed"
RELEASE_DATE_REVIEW_NOTE = (
    "Release date format was malformed or unsupported. Review preserved release chronology."
)
CREATOR_LIST_REVIEW_NOTE_TEMPLATE = (
    "{role} list format was malformed or unsupported. Review preserved creator values."
)
TEXTUAL_MONTH_MAP = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


@dataclass(frozen=True)
class NormalizedValue:
    raw_value: str | None
    canonical_value: str | None
    review_required: bool = False
    decision: str = "unchanged"
    note: str | None = None


@dataclass(frozen=True)
class ParsedReleaseDate:
    raw_value: str | None
    parsed_date: date | None
    parsed_year: int | None
    review_required: bool = False
    decision: str = "unchanged"
    note: str | None = None


@dataclass(frozen=True)
class NormalizedCreatorValue:
    raw_value: str | None
    canonical_value: str | None
    normalized_value: str | None
    review_required: bool = False
    decision: str = "unchanged"
    note: str | None = None


@dataclass(frozen=True)
class NormalizedCreatorList:
    raw_values: list[str] | None
    canonical_values: list[str] | None
    normalized_values: list[str] | None
    review_required: bool = False
    decision: str = "unchanged"
    note: str | None = None


def _normalize_spaces(value: str | None) -> str:
    if value is None:
        return ""
    normalized = value.replace("\u2013", "-").replace("\u2014", "-").replace("\u2019", "'")
    return re.sub(r"\s+", " ", normalized).strip()


def _smart_title_case(value: str) -> str:
    if not value:
        return value
    if value != value.lower() and value != value.upper():
        return value

    def transform_token(token: str) -> str:
        if not token or not any(char.isalpha() for char in token):
            return token
        return token[:1].upper() + token[1:].lower()

    parts = re.split(r"([:/\-& ])", value)
    return "".join(
        transform_token(part) if index % 2 == 0 else part
        for index, part in enumerate(parts)
    )


def _normalize_search_key(value: str | None) -> str:
    normalized = _normalize_spaces(value).lower()
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


def _normalize_creator_display(value: str | None) -> str:
    normalized = _normalize_spaces(value)
    normalized = re.sub(r"\s*,\s*", ", ", normalized)
    normalized = re.sub(r"\s*&\s*", " & ", normalized)
    normalized = re.sub(r"\s*/\s*", " / ", normalized)
    normalized = re.sub(r"(?<![A-Za-z])([A-Za-z])\.(?=\s|$)", r"\1", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _normalize_creator_lookup_name(value: str | None) -> str:
    normalized = _normalize_creator_display(value).lower()
    normalized = normalized.replace(".", "").replace(",", " ")
    normalized = re.sub(r"[^a-z0-9'&\- ]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_creator_name(
    value: str | None,
    *,
    session: Session | None = None,
) -> NormalizedCreatorValue:
    raw_value = _normalize_creator_display(value) or None
    if raw_value is None:
        return NormalizedCreatorValue(
            raw_value=None,
            canonical_value=None,
            normalized_value=None,
            decision="missing",
        )

    canonical_source = raw_value
    if session is not None:
        database_alias = get_active_db_alias_value(
            session,
            alias_type="creator",
            alias_value=raw_value,
        )
        if database_alias is not None:
            canonical_source = database_alias

    display_value = _normalize_creator_display(canonical_source)
    if display_value == display_value.lower() or display_value == display_value.upper():
        canonical_value = _smart_title_case(display_value)
    else:
        letter_count = sum(1 for char in display_value if char.isalpha())
        uppercase_count = sum(1 for char in display_value if char.isupper())
        lowercase_count = sum(1 for char in display_value if char.islower())
        if (
            letter_count > 0
            and uppercase_count > 1
            and lowercase_count > 1
            and not re.search(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+)+\b", display_value)
        ):
            canonical_value = _smart_title_case(display_value.lower())
        else:
            canonical_value = display_value
    normalized_value = _normalize_creator_lookup_name(canonical_value)
    if not normalized_value:
        return NormalizedCreatorValue(
            raw_value=raw_value,
            canonical_value=raw_value,
            normalized_value=None,
            review_required=True,
            decision="preserved_malformed",
            note="Creator name was malformed or unsupported. Review preserved creator value.",
        )

    decision = "database_alias" if canonical_source != raw_value else "normalized"
    if canonical_value == raw_value and decision == "normalized":
        decision = "unchanged"
    return NormalizedCreatorValue(
        raw_value=raw_value,
        canonical_value=canonical_value,
        normalized_value=normalized_value,
        decision=decision,
    )


def _creator_entry_looks_malformed(value: str) -> bool:
    if "??" in value:
        return True
    return bool(re.search(r"\s(?:/|;|\||&|\band\b)\s", value, flags=re.IGNORECASE))


def normalize_creator_list(
    values: list[str] | None,
    *,
    role_label: str,
    session: Session | None = None,
) -> NormalizedCreatorList:
    raw_values = [_normalize_creator_display(value) for value in (values or [])]
    raw_values = [value for value in raw_values if value]
    if not raw_values:
        return NormalizedCreatorList(
            raw_values=None,
            canonical_values=None,
            normalized_values=None,
            decision="missing",
        )

    review_notes: list[str] = []
    if any(_creator_entry_looks_malformed(value) for value in raw_values):
        review_notes.append(CREATOR_LIST_REVIEW_NOTE_TEMPLATE.format(role=role_label.capitalize()))

    canonical_values: list[str] = []
    normalized_values: list[str] = []
    seen_normalized: set[str] = set()
    for raw_value in raw_values:
        normalized = normalize_creator_name(raw_value, session=session)
        if normalized.note:
            review_notes.append(normalized.note)
        if normalized.canonical_value is None or normalized.normalized_value is None:
            continue
        if normalized.normalized_value in seen_normalized:
            continue
        seen_normalized.add(normalized.normalized_value)
        canonical_values.append(normalized.canonical_value)
        normalized_values.append(normalized.normalized_value)

    decision = "normalized"
    if canonical_values == raw_values:
        decision = "unchanged"
    return NormalizedCreatorList(
        raw_values=raw_values or None,
        canonical_values=canonical_values or None,
        normalized_values=normalized_values or None,
        review_required=bool(review_notes),
        decision=decision,
        note=" ".join(dict.fromkeys(review_notes)) if review_notes else None,
    )


def compose_variant_source_text(
    cover_name: str | None,
    printing: str | None,
    ratio: str | None,
    variant_type: str | None,
) -> str | None:
    combined = " / ".join(
        value
        for value in [
            _normalize_spaces(cover_name),
            _normalize_spaces(printing),
            _normalize_spaces(ratio),
            _normalize_spaces(variant_type),
        ]
        if value
    )
    return combined or None


def build_metadata_identity_components(
    *,
    publisher: str | None,
    series_title: str | None,
    issue_number: str | None,
    variant: str | None,
) -> MetadataIdentityComponents:
    return MetadataIdentityComponents(
        publisher=_normalize_spaces(publisher),
        series_title=_normalize_spaces(series_title),
        issue_number=_normalize_spaces(issue_number),
        variant=_normalize_spaces(variant),
    )


def build_metadata_identity_key(
    components: MetadataIdentityComponents,
) -> str:
    return "|".join(
        [
            components.publisher,
            components.series_title,
            components.issue_number,
            components.variant,
        ]
    )


def normalize_publisher_name(
    value: str | None,
    *,
    session: Session | None = None,
) -> NormalizedValue:
    raw_value = _normalize_spaces(value) or None
    if raw_value is None:
        return NormalizedValue(
            raw_value=None,
            canonical_value=None,
            review_required=True,
            decision="missing",
            note="Publisher missing after parse.",
        )

    alias_key = normalize_alias_lookup_key(raw_value)
    if session is not None:
        database_alias = get_active_db_alias_value(
            session,
            alias_type="publisher",
            alias_value=raw_value,
        )
        if database_alias is not None:
            return NormalizedValue(
                raw_value=raw_value,
                canonical_value=database_alias,
                decision="database_alias",
            )

    if alias_key in STATIC_PUBLISHER_ALIAS_MAP:
        canonical_value = STATIC_PUBLISHER_ALIAS_MAP[alias_key]
        decision = "alias_map" if canonical_value != raw_value else "known_exact"
        return NormalizedValue(
            raw_value=raw_value,
            canonical_value=canonical_value,
            decision=decision,
        )

    return NormalizedValue(
        raw_value=raw_value,
        canonical_value=raw_value,
        review_required=True,
        decision="preserved_unknown",
        note="Publisher preserved from raw parse. Review canonical publisher if needed.",
    )


def normalize_series_title(value: str | None) -> NormalizedValue:
    return normalize_series_title_with_aliases(value, session=None)


def normalize_series_title_with_aliases(
    value: str | None,
    *,
    session: Session | None = None,
) -> NormalizedValue:
    raw_value = _normalize_spaces(value) or None
    if raw_value is None:
        return NormalizedValue(
            raw_value=None,
            canonical_value=None,
            review_required=True,
            decision="missing",
            note="Series title missing after parse.",
        )

    if session is not None:
        database_alias = get_active_db_alias_value(
            session,
            alias_type="series",
            alias_value=raw_value,
        )
        if database_alias is not None:
            return NormalizedValue(
                raw_value=raw_value,
                canonical_value=database_alias,
                decision="database_alias",
            )

    canonical_value = _smart_title_case(raw_value)
    decision = "title_case" if canonical_value != raw_value else "unchanged"
    return NormalizedValue(
        raw_value=raw_value,
        canonical_value=canonical_value,
        decision=decision,
    )


def normalize_issue_number(value: str | None) -> NormalizedValue:
    raw_value = _normalize_spaces(value) or None
    if raw_value is None:
        return NormalizedValue(
            raw_value=None,
            canonical_value=None,
            review_required=True,
            decision="missing",
            note="Issue number missing after parse.",
        )

    notes: list[str] = []
    working_value = raw_value
    had_prefix = bool(ISSUE_PREFIX_PATTERN.match(working_value))
    had_hash = "#" in working_value
    if had_prefix:
        working_value = ISSUE_PREFIX_PATTERN.sub("", working_value).strip()
    if had_hash:
        working_value = working_value.replace("#", "").strip()
    if had_prefix and had_hash:
        notes.append(ISSUE_FORMAT_REVIEW_NOTE)

    compact_value = re.sub(r"\s+", "", working_value)
    compact_value = compact_value.replace(".", "")
    compact_key = compact_value.lower()

    if compact_key in SPECIAL_ISSUE_IDENTIFIERS:
        canonical_value = SPECIAL_ISSUE_IDENTIFIERS[compact_key]
    else:
        annual_match = ISSUE_ANNUAL_PATTERN.match(working_value)
        if annual_match:
            annual_remainder = _normalize_spaces(annual_match.group(1))
            annual_compact = re.sub(r"\s+", "", annual_remainder).replace(".", "")
            annual_key = annual_compact.lower()
            if annual_key in SPECIAL_ISSUE_IDENTIFIERS:
                canonical_remainder = SPECIAL_ISSUE_IDENTIFIERS[annual_key]
            else:
                annual_numeric_match = NUMERIC_ISSUE_PATTERN.fullmatch(annual_compact)
                if annual_numeric_match:
                    numeric_part = str(int(annual_numeric_match.group(1)))
                    suffix = (annual_numeric_match.group(2) or "").upper()
                    canonical_remainder = f"{numeric_part}{suffix}"
                else:
                    canonical_remainder = annual_remainder
                    notes.append(ISSUE_LOW_CONFIDENCE_REVIEW_NOTE)
            canonical_value = f"Annual {canonical_remainder}"
        else:
            if any(token in working_value for token in ["/", ",", ":"]):
                notes.append(ISSUE_LOW_CONFIDENCE_REVIEW_NOTE)

            matched = NUMERIC_ISSUE_PATTERN.fullmatch(compact_value)
            if matched:
                numeric_part = str(int(matched.group(1)))
                suffix = (matched.group(2) or "").upper()
                canonical_value = f"{numeric_part}{suffix}"
            elif compact_key in SPECIAL_ISSUE_IDENTIFIERS:
                canonical_value = SPECIAL_ISSUE_IDENTIFIERS[compact_key]
            else:
                canonical_value = working_value
                notes.append(ISSUE_LOW_CONFIDENCE_REVIEW_NOTE)

    decision = "normalized" if canonical_value != raw_value else "unchanged"
    return NormalizedValue(
        raw_value=raw_value,
        canonical_value=canonical_value,
        review_required=bool(notes),
        decision=decision,
        note=" ".join(dict.fromkeys(notes)) if notes else None,
    )


def normalize_variant_text(value: str | None) -> NormalizedValue:
    raw_value = _normalize_spaces(value) or None
    if raw_value is None:
        return NormalizedValue(raw_value=None, canonical_value=None, decision="missing")

    notes: list[str] = []
    raw_segments = [segment.strip() for segment in raw_value.split("/")]
    if any(not segment for segment in raw_segments):
        notes.append(VARIANT_MALFORMED_REVIEW_NOTE)

    canonical_segments: list[str] = []
    for raw_segment in raw_segments:
        if not raw_segment:
            continue

        segment = _normalize_spaces(raw_segment)
        segment = re.sub(r"\s*-\s*", " - ", segment)
        ratio_match = RATIO_SEGMENT_PATTERN.fullmatch(segment)
        if ratio_match:
            canonical_segments.append(f"1:{ratio_match.group(1)}")
            continue

        cover_match = (
            COVER_PREFIX_PATTERN.fullmatch(segment)
            or COVER_SUFFIX_PATTERN.fullmatch(segment)
        )
        if cover_match:
            canonical_segments.append(f"Cover {cover_match.group(1).upper()}")
            continue

        if segment.lower() in {"cover", "cvr", "variant"}:
            notes.append(VARIANT_MALFORMED_REVIEW_NOTE)

        normalized_segment = re.sub(r"\bcvr\b", "Cover", segment, flags=re.IGNORECASE)
        normalized_segment = re.sub(
            r"\ba\s+cover\b",
            "Cover A",
            normalized_segment,
            flags=re.IGNORECASE,
        )
        normalized_segment = re.sub(
            r"\b([A-Za-z0-9]+)\s+cover\b",
            lambda match: f"Cover {match.group(1).upper()}",
            normalized_segment,
            flags=re.IGNORECASE,
        )
        normalized_segment = re.sub(
            r"\bvirgin\s+variant\b",
            "Virgin Variant",
            normalized_segment,
            flags=re.IGNORECASE,
        )
        normalized_segment = re.sub(r"\bfoil\b", "Foil", normalized_segment, flags=re.IGNORECASE)
        normalized_segment = re.sub(
            r"\bvariant\b",
            "Variant",
            normalized_segment,
            flags=re.IGNORECASE,
        )
        normalized_segment = _smart_title_case(normalized_segment.lower())
        canonical_segments.append(normalized_segment)

    if "??" in raw_value or "|" in raw_value:
        notes.append(VARIANT_MALFORMED_REVIEW_NOTE)

    canonical_value = " / ".join(canonical_segments)
    canonical_value = re.sub(r"\s+", " ", canonical_value).strip()
    decision = "normalized" if canonical_value != raw_value else "unchanged"
    return NormalizedValue(
        raw_value=raw_value,
        canonical_value=canonical_value,
        review_required=bool(notes),
        decision=decision,
        note=" ".join(dict.fromkeys(notes)) if notes else None,
    )


def _valid_release_year(value: int) -> bool:
    return 1800 <= value <= 2999


def _date_from_parts(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_release_date(value: str | None) -> ParsedReleaseDate:
    raw_value = _normalize_spaces(value) or None
    if raw_value is None:
        return ParsedReleaseDate(
            raw_value=None,
            parsed_date=None,
            parsed_year=None,
            decision="missing",
        )

    year_only_match = re.fullmatch(r"(\d{4})", raw_value)
    if year_only_match:
        year = int(year_only_match.group(1))
        if _valid_release_year(year):
            return ParsedReleaseDate(
                raw_value=raw_value,
                parsed_date=None,
                parsed_year=year,
                decision="year_only",
            )

    year_month_day_match = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", raw_value)
    if year_month_day_match:
        year = int(year_month_day_match.group(1))
        month = int(year_month_day_match.group(2))
        day = int(year_month_day_match.group(3))
        exact_date = _date_from_parts(year, month, day)
        if exact_date is not None and _valid_release_year(year):
            return ParsedReleaseDate(
                raw_value=raw_value,
                parsed_date=exact_date,
                parsed_year=year,
                decision="exact_date",
            )

    year_month_match = re.fullmatch(r"(\d{4})[-/.](\d{1,2})", raw_value)
    if year_month_match:
        year = int(year_month_match.group(1))
        month = int(year_month_match.group(2))
        if _valid_release_year(year) and 1 <= month <= 12:
            return ParsedReleaseDate(
                raw_value=raw_value,
                parsed_date=None,
                parsed_year=year,
                decision="year_month_partial",
            )

    textual_month_day_match = re.fullmatch(
        r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})",
        raw_value,
    )
    if textual_month_day_match:
        month_token = textual_month_day_match.group(1).lower()
        day = int(textual_month_day_match.group(2))
        year = int(textual_month_day_match.group(3))
        month = TEXTUAL_MONTH_MAP.get(month_token)
        exact_date = _date_from_parts(year, month or 0, day) if month else None
        if exact_date is not None and _valid_release_year(year):
            return ParsedReleaseDate(
                raw_value=raw_value,
                parsed_date=exact_date,
                parsed_year=year,
                decision="textual_exact_date",
            )

    textual_month_year_match = re.fullmatch(r"([A-Za-z]+)\s+(\d{4})", raw_value)
    if textual_month_year_match:
        month_token = textual_month_year_match.group(1).lower()
        year = int(textual_month_year_match.group(2))
        if TEXTUAL_MONTH_MAP.get(month_token) and _valid_release_year(year):
            return ParsedReleaseDate(
                raw_value=raw_value,
                parsed_date=None,
                parsed_year=year,
                decision="textual_month_partial",
            )

    return ParsedReleaseDate(
        raw_value=raw_value,
        parsed_date=None,
        parsed_year=None,
        review_required=True,
        decision="preserved_malformed",
        note=RELEASE_DATE_REVIEW_NOTE,
    )


def _infer_publisher_from_source_text(title: str | None, raw_text: str) -> str | None:
    title_key = _normalize_search_key(title)
    if not title_key or not raw_text.strip():
        return None

    for raw_line in raw_text.splitlines():
        line_key = _normalize_search_key(raw_line)
        if not line_key or title_key not in line_key:
            continue

        matched_publishers = [
            publisher
            for publisher, pattern in SOURCE_LINE_PUBLISHER_MARKERS.items()
            if pattern.search(raw_line)
        ]
        if len(matched_publishers) == 1:
            return matched_publishers[0]

    return None


def _infer_publisher_from_title(title: str | None) -> str | None:
    title_key = _normalize_search_key(title)
    if not title_key:
        return None

    for publisher, hints in HIGH_CONFIDENCE_TITLE_PUBLISHERS.items():
        if any(hint in title_key for hint in hints):
            return publisher
    return None


def _item_review_label(index: int, title: str | None, issue_number: str | None) -> str:
    title_label = _normalize_spaces(title) or "Untitled item"
    issue_label = _normalize_spaces(issue_number)
    if issue_label:
        return f"{index} ({title_label} #{issue_label})"
    return f"{index} ({title_label})"


def enrich_order_item_metadata(
    item: AiDraftOrderItem,
    *,
    session: Session | None = None,
    owner_user_id: int | None = None,
    raw_text: str,
    item_index: int,
) -> AiDraftOrderItem:
    if item.raw_publisher is not None:
        raw_publisher_source = item.raw_publisher
    elif item.metadata_autofill_source is not None:
        raw_publisher_source = None
    else:
        raw_publisher_source = item.publisher
    raw_title_source = item.raw_title if item.raw_title is not None else item.title
    raw_release_date_source = (
        item.raw_release_date
        if item.raw_release_date is not None
        else item.release_date
    )
    raw_issue_source = (
        item.raw_issue_number if item.raw_issue_number is not None else item.issue_number
    )
    raw_writers_source = item.raw_writers if item.raw_writers is not None else item.writers
    raw_artists_source = item.raw_artists if item.raw_artists is not None else item.artists
    raw_cover_artists_source = (
        item.raw_cover_artists
        if item.raw_cover_artists is not None
        else (
            item.cover_artists
            if item.cover_artists is not None
            else [item.cover_artist]
            if item.cover_artist
            else None
        )
    )

    title = normalize_series_title_with_aliases(raw_title_source, session=session)
    release_date = parse_release_date(raw_release_date_source)
    issue_number = normalize_issue_number(raw_issue_source)
    writers = normalize_creator_list(raw_writers_source, role_label="writer", session=session)
    artists = normalize_creator_list(raw_artists_source, role_label="artist", session=session)
    cover_artists = normalize_creator_list(
        raw_cover_artists_source,
        role_label="cover artist",
        session=session,
    )

    publisher = normalize_publisher_name(raw_publisher_source, session=session)
    metadata_autofill_source = item.metadata_autofill_source
    publisher_autofill_confidence = item.publisher_autofill_confidence
    if publisher.decision == "missing" and session is not None and title.canonical_value:
        autofill = resolve_blank_publisher(
            session,
            owner_user_id=owner_user_id,
            canonical_series=title.canonical_value,
            canonical_issue=issue_number.canonical_value,
            raw_text=raw_text,
        )
        if autofill is not None:
            publisher = NormalizedValue(
                raw_value=publisher.raw_value,
                canonical_value=autofill.publisher,
                review_required=False,
                decision=f"autofill_{autofill.source}",
            )
            metadata_autofill_source = autofill.source
            publisher_autofill_confidence = autofill.confidence

    raw_variant_text = item.raw_variant_text
    if raw_variant_text is None:
        raw_variant_text = compose_variant_source_text(
            item.cover_name,
            item.printing,
            item.ratio,
            item.variant_type,
        )
    variant_text = normalize_variant_text(raw_variant_text)
    cover_name = normalize_variant_text(item.cover_name)
    printing = normalize_variant_text(item.printing)
    ratio = normalize_variant_text(item.ratio)
    variant_type = normalize_variant_text(item.variant_type)
    release_status = item.release_status or default_release_status(
        release_date=release_date.parsed_date
    )
    order_status = default_order_status(
        release_status=release_status,
        received_at=item.received_at,
        explicit_order_status=item.order_status,
    )
    expected_ship_date = default_expected_ship_date(
        release_date=release_date.parsed_date,
        release_status=release_status,
        explicit_expected_ship_date=item.expected_ship_date,
    )
    metadata_identity_components = build_metadata_identity_components(
        publisher=publisher.canonical_value,
        series_title=title.canonical_value,
        issue_number=issue_number.canonical_value,
        variant=variant_text.canonical_value,
    )
    metadata_identity_key = build_metadata_identity_key(metadata_identity_components)

    review_notes = [
        note
        for note in [
            publisher.note,
            title.note,
            release_date.note,
            issue_number.note,
            writers.note,
            artists.note,
            cover_artists.note,
            variant_text.note,
        ]
        if note
    ]
    review_required = (
        publisher.review_required
        or title.review_required
        or release_date.review_required
        or issue_number.review_required
        or writers.review_required
        or artists.review_required
        or cover_artists.review_required
        or variant_text.review_required
    )

    LOGGER.info(
        (
            "Metadata enrichment item=%s publisher=%r->%r title=%r->%r "
            "release=%r->%r/%r issue=%r->%r variant=%r->%r review=%s"
        ),
        item_index,
        publisher.raw_value,
        publisher.canonical_value,
        title.raw_value,
        title.canonical_value,
        release_date.raw_value,
        release_date.parsed_date,
        release_date.parsed_year,
        issue_number.raw_value,
        issue_number.canonical_value,
        variant_text.raw_value,
        variant_text.canonical_value,
        review_required,
    )

    return item.model_copy(
        update={
            "publisher": publisher.canonical_value,
            "raw_publisher": publisher.raw_value,
            "canonical_publisher": publisher.canonical_value,
            "title": title.canonical_value,
            "raw_title": title.raw_value,
            "canonical_title": title.canonical_value,
            "release_date": release_date.raw_value,
            "raw_release_date": release_date.raw_value,
            "parsed_release_date": release_date.parsed_date,
            "parsed_release_year": release_date.parsed_year,
            "release_status": release_status,
            "order_status": order_status,
            "expected_ship_date": expected_ship_date,
            "issue_number": issue_number.canonical_value,
            "raw_issue_number": issue_number.raw_value,
            "canonical_issue_number": issue_number.canonical_value,
            "cover_name": cover_name.canonical_value,
            "printing": printing.canonical_value,
            "ratio": ratio.canonical_value,
            "variant_type": variant_type.canonical_value,
            "writers": writers.canonical_values,
            "raw_writers": writers.raw_values,
            "canonical_writers": writers.canonical_values,
            "artists": artists.canonical_values,
            "raw_artists": artists.raw_values,
            "canonical_artists": artists.canonical_values,
            "cover_artists": cover_artists.canonical_values,
            "raw_cover_artists": cover_artists.raw_values,
            "canonical_cover_artists": cover_artists.canonical_values,
            "cover_artist": (
                ", ".join(cover_artists.canonical_values)
                if cover_artists.canonical_values
                else item.cover_artist
            ),
            "raw_variant_text": variant_text.raw_value,
            "canonical_variant_text": variant_text.canonical_value,
            "metadata_identity_key": metadata_identity_key,
            "metadata_identity_components": metadata_identity_components,
            "metadata_review_required": review_required,
            "metadata_review_notes": review_notes,
            "metadata_autofill_source": metadata_autofill_source,
            "publisher_autofill_confidence": publisher_autofill_confidence,
        }
    )


def enrich_parse_order_metadata(
    parsed: ParseOrderResponse,
    *,
    session: Session | None = None,
    owner_user_id: int | None = None,
    raw_text: str,
) -> ParseOrderResponse:
    enriched_items = [
        enrich_order_item_metadata(
            item,
            session=session,
            owner_user_id=owner_user_id,
            raw_text=raw_text,
            item_index=index,
        )
        for index, item in enumerate(parsed.items, start=1)
    ]

    warnings = list(parsed.warnings)
    review_labels = [
        _item_review_label(index, item.title, item.issue_number)
        for index, item in enumerate(enriched_items, start=1)
        if item.metadata_review_required
    ]
    warnings = [
        warning
        for warning in warnings
        if not warning.startswith(PUBLISHER_REVIEW_WARNING_PREFIX)
    ]
    if review_labels:
        warnings.append(f"{PUBLISHER_REVIEW_WARNING_PREFIX} " + "; ".join(review_labels) + ".")

    order_purchase_date = parsed.order_date
    purchase_enriched_items = [
        item.model_copy(
            update={
                "purchase_date": item.purchase_date or order_purchase_date,
            }
        )
        for item in enriched_items
    ]
    return parsed.model_copy(update={"items": purchase_enriched_items, "warnings": warnings})


def iter_canonical_creator_names(item: AiDraftOrderItem) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for creator_list in [
        item.canonical_writers or item.writers,
        item.canonical_artists or item.artists,
        item.canonical_cover_artists or item.cover_artists,
    ]:
        for creator_name in creator_list or []:
            key = _normalize_creator_lookup_name(creator_name)
            if not key or key in seen:
                continue
            seen.add(key)
            names.append(creator_name)
    return names
