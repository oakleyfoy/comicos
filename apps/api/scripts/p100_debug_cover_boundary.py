"""Debug P100-19 cover boundary detection for a local image."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from app.services.photo_import_cover_boundary_service import refine_cover_boundary  # noqa: E402
from app.services.photo_import_crop_service import expand_bbox_for_comic_crop  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="P100-19 cover boundary debug")
    parser.add_argument("--image", required=True)
    parser.add_argument("--bbox", default="0.1,0.1,0.25,0.8", help="x,y,width,height normalized")
    parser.add_argument("--out", default="cover_boundary_debug.jpg")
    args = parser.parse_args()
    path = Path(args.image)
    parts = [float(p) for p in args.bbox.split(",")]
    original = {"x": parts[0], "y": parts[1], "width": parts[2], "height": parts[3]}
    expanded = expand_bbox_for_comic_crop(original)
    with Image.open(path) as img:
        w, h = img.size
        result = refine_cover_boundary(
            path,
            original_bbox=original,
            expanded_bbox=expanded,
            image_width=w,
            image_height=h,
        )
        draw = img.convert("RGB")
        overlay = ImageDraw.Draw(draw)
        for label, box, color in (
            ("orig", original, "red"),
            ("exp", expanded, "yellow"),
            ("ref", result.refined_bbox, "lime"),
        ):
            x0 = int(box["x"] * w)
            y0 = int(box["y"] * h)
            x1 = int((box["x"] + box["width"]) * w)
            y1 = int((box["y"] + box["height"]) * h)
            overlay.rectangle([x0, y0, x1, y1], outline=color, width=3)
            overlay.text((x0 + 2, y0 + 2), label, fill=color)
        out = Path(args.out)
        draw.save(out, format="JPEG", quality=92)
    print(
        {
            "original_bbox": original,
            "expanded_bbox": expanded,
            "refined_bbox": result.refined_bbox,
            "confidence": result.boundary_confidence,
            "method": result.boundary_method,
            "corners": result.cover_corners,
            "annotated": str(out),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
