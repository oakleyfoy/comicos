"""P89-03 rule-based listing descriptions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DescriptionInputs:
    display_title: str
    publisher: str
    issue_number: str
    variant: str
    grade_condition: str
    key_notes: list[str]
    condition_paragraph: str
    shipping_paragraph: str


def generate_listing_description(inputs: DescriptionInputs) -> str:
    lines = [inputs.display_title.strip() or "Comic book listing", "", "Details:", ""]
    if inputs.publisher.strip():
        lines.append(f"• Publisher: {inputs.publisher.strip()}")
    if inputs.issue_number.strip():
        lines.append(f"• Issue: {inputs.issue_number.strip()}")
    if inputs.variant.strip() and inputs.variant.strip().lower() != "standard":
        lines.append(f"• Variant: {inputs.variant.strip()}")
    if inputs.grade_condition.strip():
        lines.append(f"• Grade/Condition: {inputs.grade_condition.strip()}")
    for note in inputs.key_notes:
        n = note.strip()
        if n:
            lines.append(f"• Key Notes: {n}")
    lines.extend(["", "Condition:", inputs.condition_paragraph.strip() or "Please review photos for condition.", ""])
    lines.extend(["Shipping:", inputs.shipping_paragraph.strip() or "Ships bagged and boarded in a protective comic mailer."])
    return "\n".join(lines)
