"""Multi-frame supplement OCR: per-digit weighted voting across consecutive reads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SupplementFrameRead:
    frame_index: int
    digits: str
    confidence: float
    source: str = "ocr"

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "digits": self.digits,
            "confidence": round(self.confidence, 3),
            "source": self.source,
        }


@dataclass
class SupplementDigitVote:
    position: int
    winner: str
    winner_weight: float
    total_weight: float
    rejected: bool
    tally: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "position": self.position,
            "winner": self.winner,
            "winner_weight": round(self.winner_weight, 4),
            "total_weight": round(self.total_weight, 4),
            "rejected": self.rejected,
            "tally": {k: round(v, 4) for k, v in self.tally.items()},
        }


@dataclass
class SupplementConsensusResult:
    digits: str
    confidence: float
    complete: bool
    frame_reads: list[SupplementFrameRead] = field(default_factory=list)
    position_votes: list[SupplementDigitVote] = field(default_factory=list)
    review_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "digits": self.digits,
            "confidence": round(self.confidence, 3),
            "complete": self.complete,
            "frame_reads": [f.to_dict() for f in self.frame_reads],
            "position_votes": [p.to_dict() for p in self.position_votes],
            "review_reason": self.review_reason,
        }


# Winner must hold at least this share of weighted votes at a digit position.
MIN_POSITION_WEIGHT_SHARE = 0.40
# Per-frame confidence below this does not contribute weight at a position.
MIN_FRAME_CONFIDENCE = 0.05


def vote_supplement_digits(
    frame_reads: list[SupplementFrameRead],
    *,
    min_weight_share: float = MIN_POSITION_WEIGHT_SHARE,
) -> SupplementConsensusResult:
    """Character-by-character weighted vote across 5-digit supplement OCR reads."""
    valid = [r for r in frame_reads if len(r.digits) == 5 and r.digits.isdigit()]
    if not valid:
        return SupplementConsensusResult(
            digits="",
            confidence=0.0,
            complete=False,
            frame_reads=list(frame_reads),
            review_reason="No valid 5-digit supplement reads across frames.",
        )

    chars: list[str] = []
    position_votes: list[SupplementDigitVote] = []
    confidences: list[float] = []

    for pos in range(5):
        tally: dict[str, float] = {}
        for read in valid:
            weight = max(0.0, float(read.confidence))
            if weight < MIN_FRAME_CONFIDENCE:
                continue
            ch = read.digits[pos]
            tally[ch] = tally.get(ch, 0.0) + weight
        total = sum(tally.values())
        if total <= 0:
            position_votes.append(
                SupplementDigitVote(
                    position=pos,
                    winner="",
                    winner_weight=0.0,
                    total_weight=0.0,
                    rejected=True,
                    tally=tally,
                )
            )
            chars.append("?")
            continue
        winner = max(tally, key=tally.get)
        winner_weight = tally[winner]
        share = winner_weight / total
        rejected = share < min_weight_share
        position_votes.append(
            SupplementDigitVote(
                position=pos,
                winner=winner if not rejected else "?",
                winner_weight=winner_weight,
                total_weight=total,
                rejected=rejected,
                tally=tally,
            )
        )
        if rejected:
            chars.append("?")
        else:
            chars.append(winner)
            confidences.append(share)

    digits = "".join(chars)
    complete = len(digits) == 5 and "?" not in digits
    confidence = (sum(confidences) / len(confidences)) if confidences else 0.0
    review = ""
    if not complete:
        review = (
            f"Supplement digit consensus incomplete ({digits}); "
            "one or more positions lacked confident agreement across frames."
        )
    return SupplementConsensusResult(
        digits=digits if complete else "",
        confidence=confidence,
        complete=complete,
        frame_reads=list(frame_reads),
        position_votes=position_votes,
        review_reason=review,
    )
