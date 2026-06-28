"""Intake worker merges 12-digit UPC with supplement decodes from burst frames."""

from __future__ import annotations

from unittest.mock import patch

from app.services.intake_worker_service import _merge_seventeen_digit_from_image_frames


def test_merge_seventeen_digit_from_burst_frames() -> None:
    main = "761568002140"
    full = "76156800214000211"

    def fake_decode(_fb: bytes) -> tuple[str, str] | None:
        return (full, "test")

    with patch(
        "app.services.intake_worker_service.decode_upc_from_image_bytes",
        side_effect=fake_decode,
    ):
        merged = _merge_seventeen_digit_from_image_frames(
            main=main,
            frame_bytes_list=[b"primary", b"frame1", b"frame2"],
        )
    assert merged == full


def test_merge_ignores_unrelated_upc_on_frame() -> None:
    main = "761568002140"

    def fake_decode(_fb: bytes) -> tuple[str, str] | None:
        return (main, "twelve_only")

    with patch(
        "app.services.intake_worker_service.decode_upc_from_image_bytes",
        side_effect=fake_decode,
    ):
        with patch(
            "app.services.intake_worker_service.collect_raw_upc_candidates_from_pil",
            return_value=[],
        ):
            merged = _merge_seventeen_digit_from_image_frames(
                main=main,
                frame_bytes_list=[b"primary"],
            )
    assert merged is None
