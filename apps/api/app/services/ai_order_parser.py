import json
from decimal import Decimal
from urllib import error, request

from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.schemas.ai import AiDraftOrderItem, ParseOrderResponse


class AiOrderParserError(Exception):
    pass


class AiOrderParserNotConfiguredError(AiOrderParserError):
    pass


def ensure_ai_parser_configured(settings: Settings | None = None) -> Settings:
    resolved_settings = settings or get_settings()
    if not resolved_settings.openai_api_key:
        raise AiOrderParserNotConfiguredError("AI parser is not configured.")
    return resolved_settings


SYSTEM_PROMPT = """You extract draft comic purchase orders from pasted receipt and invoice text.

Rules:
- Produce a draft order only.
- Never invent missing comic details.
- Prefer null over guessed values for uncertain text fields.
- Never invent prices.
- Never invent ratios.
- Use null when price, ratio, retailer, issue number, quantity, or variant details are uncertain.
- Always include warnings for uncertainty, ambiguity, or missing information.
- Warnings are required when price is missing, quantity is uncertain,
  retailer is uncertain, issue number is uncertain, or variant/cover
  details are uncertain.
- Normalize retailer, publisher, title, and issue formatting when clearly present.
- Quantity must be null when uncertain, otherwise at least 1.
- raw_item_price must be null when uncertain, otherwise never negative.
- shipping_amount and tax_amount must never be negative.
- source_type must always be "ai_draft".
- Support Whatnot receipts, eBay receipts, retailer invoices, and arbitrary pasted order text.
- If the text is weak or incomplete, return the best partial draft possible with warnings.
- High confidence only when retailer, order date, title, issue number,
  quantity, and raw item price are all clearly detected.
- Medium confidence only when title, issue number, and raw item price are mostly detected.
- Low confidence when key fields are missing or uncertain.
"""


def build_json_schema() -> dict:
    return {
        "name": "comic_order_draft",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "retailer": {"type": ["string", "null"], "maxLength": 120},
                "order_date": {"type": ["string", "null"]},
                "source_type": {"type": "string", "enum": ["ai_draft"]},
                "shipping_amount": {"type": "number", "minimum": 0},
                "tax_amount": {"type": "number", "minimum": 0},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "publisher": {"type": ["string", "null"]},
                            "title": {"type": ["string", "null"]},
                            "issue_number": {"type": ["string", "null"]},
                            "cover_name": {"type": ["string", "null"]},
                            "printing": {"type": ["string", "null"]},
                            "ratio": {"type": ["string", "null"]},
                            "variant_type": {"type": ["string", "null"]},
                            "cover_artist": {"type": ["string", "null"]},
                            "quantity": {"type": ["integer", "null"], "minimum": 1},
                            "raw_item_price": {"type": ["number", "null"], "minimum": 0},
                        },
                        "required": [
                            "publisher",
                            "title",
                            "issue_number",
                            "cover_name",
                            "printing",
                            "ratio",
                            "variant_type",
                            "cover_artist",
                            "quantity",
                            "raw_item_price",
                        ],
                    },
                },
                "warnings": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": [
                "retailer",
                "order_date",
                "source_type",
                "shipping_amount",
                "tax_amount",
                "items",
                "warnings",
                "confidence_score",
            ],
        },
    }


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None

    trimmed = value.strip()
    if not trimmed:
        return None

    lowered = trimmed.lower()
    uncertain_tokens = {
        "unknown",
        "uncertain",
        "n/a",
        "na",
        "none",
        "null",
        "not provided",
        "not listed",
        "not specified",
        "tbd",
        "?",
    }
    if lowered in uncertain_tokens:
        return None

    return trimmed


def _normalize_item(item: AiDraftOrderItem) -> AiDraftOrderItem:
    return item.model_copy(
        update={
            "publisher": _clean_optional_text(item.publisher),
            "title": _clean_optional_text(item.title),
            "issue_number": _clean_optional_text(item.issue_number),
            "cover_name": _clean_optional_text(item.cover_name),
            "printing": _clean_optional_text(item.printing),
            "ratio": _clean_optional_text(item.ratio),
            "variant_type": _clean_optional_text(item.variant_type),
            "cover_artist": _clean_optional_text(item.cover_artist),
            "quantity": item.quantity if item.quantity and item.quantity >= 1 else None,
            "raw_item_price": item.raw_item_price if item.raw_item_price is not None else None,
        }
    )


def _calculate_confidence(
    retailer: str | None,
    order_date,
    items: list[AiDraftOrderItem],
) -> float:
    if not items:
        return 0.2

    retailer_detected = retailer is not None
    date_detected = order_date is not None
    titles_detected = all(item.title is not None for item in items)
    issues_detected = all(item.issue_number is not None for item in items)
    quantities_detected = all(item.quantity is not None for item in items)
    prices_detected = all(item.raw_item_price is not None for item in items)

    if (
        retailer_detected
        and date_detected
        and titles_detected
        and issues_detected
        and quantities_detected
        and prices_detected
    ):
        return 0.92

    title_issue_price_hits = sum(
        1
        for item in items
        if (
            item.title is not None
            and item.issue_number is not None
            and item.raw_item_price is not None
        )
    )
    mostly_detected = title_issue_price_hits / len(items) >= 0.6
    if mostly_detected:
        return 0.66

    return 0.28


def _merge_required_warnings(
    draft: ParseOrderResponse,
) -> ParseOrderResponse:
    warnings = [warning.strip() for warning in draft.warnings if warning and warning.strip()]
    items = [_normalize_item(item) for item in draft.items]

    retailer = _clean_optional_text(draft.retailer)
    if retailer is None:
        warnings.append("Retailer uncertain or missing. Review before confirming the draft.")

    if not items:
        warnings.append(
            "No line items were confidently extracted. Review the pasted text manually."
        )

    for index, item in enumerate(items, start=1):
        if item.raw_item_price is None:
            warnings.append(
                f"Item {index} price is missing or uncertain. "
                "Review the raw item price before confirming."
            )
        if item.quantity is None:
            warnings.append(
                f"Item {index} quantity is uncertain. Review the quantity before confirming."
            )
        if item.issue_number is None:
            warnings.append(
                f"Item {index} issue number is uncertain or missing. Review before confirming."
            )
        if item.cover_name is None and item.variant_type is None and item.printing is None:
            warnings.append(
                f"Item {index} variant or cover details are uncertain. "
                "Review cover, printing, and variant fields."
            )
        if item.ratio is None:
            warnings.append(
                f"Item {index} ratio was not confidently detected. "
                "Leave it blank unless the receipt clearly shows one."
            )

    confidence_score = _calculate_confidence(
        retailer=retailer,
        order_date=draft.order_date,
        items=items,
    )

    deduped_warnings: list[str] = []
    for warning in warnings:
        if warning not in deduped_warnings:
            deduped_warnings.append(warning)

    normalized = draft.model_copy(
        update={
            "retailer": retailer,
            "source_type": "ai_draft",
            "shipping_amount": Decimal(draft.shipping_amount),
            "tax_amount": Decimal(draft.tax_amount),
            "items": items,
            "warnings": deduped_warnings,
            "confidence_score": confidence_score,
        }
    )
    return ParseOrderResponse.model_validate(normalized.model_dump())


def parse_order_draft_from_text(
    raw_text: str,
    settings: Settings | None = None,
) -> ParseOrderResponse:
    resolved_settings = ensure_ai_parser_configured(settings)

    body = {
        "model": resolved_settings.openai_order_parser_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Extract a deterministic draft order from the pasted text below. "
                    "Return only structured JSON matching the schema.\n\n"
                    f"{raw_text}"
                ),
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": build_json_schema(),
        },
    }

    http_request = request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {resolved_settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise AiOrderParserError(f"OpenAI API request failed: {detail or exc.reason}") from exc
    except error.URLError as exc:
        raise AiOrderParserError("Unable to reach OpenAI API") from exc
    except TimeoutError as exc:
        raise AiOrderParserError("OpenAI API request timed out") from exc

    try:
        message = payload["choices"][0]["message"]
        if message.get("refusal"):
            raise AiOrderParserError(f"OpenAI parser refused request: {message['refusal']}")

        parsed_content = json.loads(message["content"])
        draft = ParseOrderResponse.model_validate(parsed_content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as exc:
        raise AiOrderParserError("OpenAI API returned an invalid draft response") from exc

    return _merge_required_warnings(draft)
