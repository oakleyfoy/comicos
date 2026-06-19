"""P100-14A persist and serve per-detection crop images."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.services.photo_import_storage_service import REPO_ROOT

API_ROOT = REPO_ROOT


def clamp_bbox01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def crop_storage_dir(*, session_id: int) -> Path:
    path = REPO_ROOT / "data" / "photo_import" / "crops" / str(session_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def extract_and_save_crop(
    image_path: Path,
    bbox: dict[str, float],
    *,
    session_id: int,
    image_id: int,
    idx: int,
) -> tuple[str, tuple[int, int]]:
    """Crop source photo, save JPEG; return (repo-relative path, (width, height))."""
    crop_dir = crop_storage_dir(session_id=session_id)
    crop_name = f"{image_id}_{idx}.jpg"
    crop_path = crop_dir / crop_name
    with Image.open(image_path) as img:
        w, h = img.size
        x = int(clamp_bbox01(bbox.get("x", 0)) * w)
        y = int(clamp_bbox01(bbox.get("y", 0)) * h)
        bw = max(1, int(clamp_bbox01(bbox.get("width", 1)) * w))
        bh = max(1, int(clamp_bbox01(bbox.get("height", 1)) * h))
        cropped = img.crop((x, y, min(w, x + bw), min(h, y + bh)))
        cropped.convert("RGB").save(crop_path, format="JPEG", quality=90)
        cw, ch = cropped.size
    rel = str(crop_path.relative_to(REPO_ROOT)).replace("\\", "/")
    return rel, (cw, ch)


def resolve_crop_abs_path(crop_path: str | None) -> Path | None:
    if not crop_path or not str(crop_path).strip():
        return None
    rel = str(crop_path).strip().lstrip("/")
    candidate = REPO_ROOT / rel
    if candidate.is_file():
        return candidate
    return None


def crop_api_path(*, detection_id: int) -> str:
    return f"/api/v1/photo-import/detections/{int(detection_id)}/crop-image"
