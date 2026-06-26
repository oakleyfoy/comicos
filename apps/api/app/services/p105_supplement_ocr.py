"""P105 left-supplement OCR retry pipeline + candidate scoring.

The printed 5-digit supplement on the left of a comic UPC/price box is the
identity signal for issue/variant. This module runs many crop/preprocessing
variants of that small region through digit-whitelisted Tesseract, then scores
the resulting candidates against repetition, confidence, catalog existence, and
cover-fingerprint agreement so that OCR substitutions (e.g. 03311 vs 00311) and
blank first passes can be corrected or flagged for review.
"""

from __future__ import annotations

import logging
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# Tesseract page-segmentation modes suited to a short numeric block.
#   7 = single text line, 8 = single word, 6 = uniform block, 13 = raw line.
_PSM_MODES: tuple[int, ...] = (7, 8, 6, 13)
_DIGIT_WHITELIST = "0123456789"
_DEFAULT_TIMEOUT = 8.0


@dataclass
class OcrAttempt:
    variant: str
    raw_text: str
    digits: str
    confidence: float
    source: str = "tesseract"

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant": self.variant,
            "raw_text": self.raw_text,
            "digits": self.digits,
            "confidence": round(self.confidence, 3),
            "source": self.source,
        }


@dataclass
class SupplementCandidate:
    digits: str
    score: float
    ocr_confidence: float
    repeat_count: int
    catalog_exists: bool = False
    fingerprint_score: float = 0.0
    publisher_agrees: bool = False
    catalog_issue_id: int | None = None
    sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "digits": self.digits,
            "score": round(self.score, 3),
            "ocr_confidence": round(self.ocr_confidence, 3),
            "repeat_count": self.repeat_count,
            "catalog_exists": self.catalog_exists,
            "fingerprint_score": round(self.fingerprint_score, 2),
            "publisher_agrees": self.publisher_agrees,
            "catalog_issue_id": self.catalog_issue_id,
            "sources": list(self.sources),
        }


def _digits_only(raw: str) -> str:
    return re.sub(r"\D", "", raw or "")


def _normalize_supplement(text: str) -> str:
    digits = _digits_only(text)
    if len(digits) == 5:
        return digits
    if 3 <= len(digits) <= 4:
        return digits
    if len(digits) > 5:
        # Prefer a trailing/leading 5-digit window; keep first 5 deterministically.
        return digits[:5]
    return ""


# ---------------------------------------------------------------------------
# Tesseract execution (digit whitelist + TSV confidence)
# ---------------------------------------------------------------------------


def _tesseract_cmd() -> str:
    try:
        from app.services.cover_images import _resolve_ocr_engine_cmd

        return _resolve_ocr_engine_cmd()
    except Exception:  # noqa: BLE001
        return "tesseract"


def _parse_tsv(stdout: str) -> tuple[str, float]:
    digits = ""
    confs: list[float] = []
    lines = stdout.splitlines()
    for line in lines[1:]:
        cols = line.split("\t")
        if len(cols) < 12:
            continue
        try:
            conf = float(cols[10])
        except ValueError:
            continue
        text = _digits_only(cols[11])
        if not text or conf < 0:
            continue
        digits += text
        confs.append(conf)
    confidence = (sum(confs) / len(confs) / 100.0) if confs else 0.0
    return digits, max(0.0, min(1.0, confidence))


def _run_tesseract_digits(pil: Image.Image, *, psm: int, timeout_seconds: float = _DEFAULT_TIMEOUT) -> tuple[str, float]:
    """Run digit-whitelisted Tesseract; return (digits, confidence 0..1)."""
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            pil.save(tmp_path)
        args = [
            _tesseract_cmd(),
            str(tmp_path),
            "stdout",
            "--psm",
            str(psm),
            "-c",
            f"tessedit_char_whitelist={_DIGIT_WHITELIST}",
            "tsv",
        ]
        result = subprocess.run(args, capture_output=True, text=True, check=False, timeout=timeout_seconds)
        if result.returncode != 0:
            return "", 0.0
        return _parse_tsv(result.stdout or "")
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("p105.tesseract_digits_fail psm=%s err=%s", psm, exc)
        return "", 0.0
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Pixel preprocessing variants
# ---------------------------------------------------------------------------


def _preprocess_variants(crop: Image.Image) -> list[tuple[str, Image.Image]]:
    gray = ImageOps.grayscale(crop)
    base_w = max(1, gray.width)
    up3 = gray.resize((max(1, base_w * 3), max(1, gray.height * 3)), Image.Resampling.LANCZOS)
    up4 = gray.resize((max(1, base_w * 4), max(1, gray.height * 4)), Image.Resampling.LANCZOS)
    contrast = ImageOps.autocontrast(up3, cutoff=2)

    def _threshold(img: Image.Image, *, invert: bool) -> Image.Image:
        pixels = list(img.getdata())
        avg = sum(pixels) / max(1, len(pixels))
        thr = int(avg)
        bw = img.point(lambda px: 255 if px > thr else 0)
        if invert:
            bw = ImageOps.invert(bw.convert("L"))
        return bw.convert("L")

    variants: list[tuple[str, Image.Image]] = [
        ("grayscale", up3),
        ("upscale4x", up4),
        ("contrast", contrast),
        ("adaptive_thresh", _threshold(contrast, invert=False)),
        ("inverted_thresh", _threshold(contrast, invert=True)),
    ]
    return variants


def _rotation_variants(crop: Image.Image, angle: float) -> list[tuple[str, Image.Image]]:
    out: list[tuple[str, Image.Image]] = []
    angles = {round(angle, 1)} if abs(angle) >= 1.0 else set()
    angles.update({-4.0, 4.0})
    for a in sorted(angles):
        if abs(a) < 0.5:
            continue
        rotated = crop.rotate(-a, expand=True, fillcolor=(255, 255, 255) if crop.mode == "RGB" else 255)
        out.append((f"rotate{a:+.0f}", rotated))
    return out


def _ocr_variant(pil: Image.Image, label: str, *, psm: int, log_context: str) -> OcrAttempt:
    """Single OCR pass on one preprocessed crop. Patch this seam in tests."""
    digits_raw, conf = _run_tesseract_digits(pil, psm=psm)
    return OcrAttempt(
        variant=f"{label}|psm{psm}",
        raw_text=digits_raw,
        digits=_normalize_supplement(digits_raw),
        confidence=conf,
        source="tesseract",
    )


def _has_repeated_five_digit(attempts: list[OcrAttempt]) -> bool:
    seen: dict[str, int] = {}
    for a in attempts:
        if len(a.digits) == 5:
            seen[a.digits] = seen.get(a.digits, 0) + 1
            if seen[a.digits] >= 2:
                return True
    return False


def gather_ocr_attempts(
    base_crops: list[tuple[str, Image.Image]],
    *,
    deskew_angle: float = 0.0,
    log_context: str = "p105_supplement",
    vision_attempt: OcrAttempt | None = None,
) -> list[OcrAttempt]:
    """Run all crop x preprocessing x PSM variants; stop early on a repeated 5-digit hit."""
    attempts: list[OcrAttempt] = []
    for crop_label, crop in base_crops:
        crop_variants: list[tuple[str, Image.Image]] = list(_preprocess_variants(crop))
        crop_variants.extend(_rotation_variants(crop, deskew_angle))
        for pp_label, pp_img in crop_variants:
            for psm in (_PSM_MODES[0], _PSM_MODES[1]):
                attempts.append(
                    _ocr_variant(pp_img, f"{crop_label}|{pp_label}", psm=psm, log_context=log_context)
                )
        if _has_repeated_five_digit(attempts):
            break
    if vision_attempt is not None:
        attempts.append(vision_attempt)
    return attempts


# ---------------------------------------------------------------------------
# Candidate scoring
# ---------------------------------------------------------------------------


def hamming5(a: str, b: str) -> int:
    if len(a) != len(b):
        return max(len(a), len(b))
    return sum(1 for x, y in zip(a, b) if x != y)


def score_supplement_candidates(
    attempts: list[OcrAttempt],
    *,
    main_upc: str,
    catalog_supplements: dict[str, int] | None = None,
    fingerprint_scorer: Any | None = None,
    publisher_prefix_ok: bool = False,
) -> list[SupplementCandidate]:
    """Aggregate 5-digit OCR attempts and rank by confidence + corroborating signals.

    ``catalog_supplements`` maps a known 5-digit supplement -> catalog issue id for
    ``main_upc``. ``fingerprint_scorer`` is an optional callable(issue_id) -> float (0..100).
    """
    catalog_supplements = catalog_supplements or {}
    agg: dict[str, SupplementCandidate] = {}
    for a in attempts:
        if len(a.digits) != 5:
            continue
        cand = agg.get(a.digits)
        if cand is None:
            cand = SupplementCandidate(
                digits=a.digits,
                score=0.0,
                ocr_confidence=a.confidence,
                repeat_count=0,
            )
            agg[a.digits] = cand
        cand.repeat_count += 1
        cand.ocr_confidence = max(cand.ocr_confidence, a.confidence)
        if a.source not in cand.sources:
            cand.sources.append(a.source)

    for digits, cand in agg.items():
        score = cand.ocr_confidence
        score += min(cand.repeat_count, 5) * 0.12
        if digits in catalog_supplements:
            cand.catalog_exists = True
            cand.catalog_issue_id = catalog_supplements[digits]
            score += 0.6
            if fingerprint_scorer is not None and cand.catalog_issue_id is not None:
                try:
                    fp = float(fingerprint_scorer(cand.catalog_issue_id))
                except Exception:  # noqa: BLE001
                    fp = 0.0
                cand.fingerprint_score = fp
                if fp >= 70.0:
                    score += 0.4
        if publisher_prefix_ok:
            cand.publisher_agrees = True
            score += 0.1
        cand.score = score

    return sorted(agg.values(), key=lambda c: (c.score, c.repeat_count, c.ocr_confidence), reverse=True)
