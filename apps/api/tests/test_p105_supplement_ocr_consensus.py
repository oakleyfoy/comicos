from app.services.p105_supplement_ocr_consensus import (
    SupplementFrameRead,
    vote_supplement_digits,
)


def test_vote_supplement_digits_user_example() -> None:
    reads = [
        SupplementFrameRead(0, "03121", 0.9),
        SupplementFrameRead(1, "03921", 0.85),
        SupplementFrameRead(2, "03921", 0.88),
        SupplementFrameRead(3, "03121", 0.87),
        SupplementFrameRead(4, "03921", 0.86),
    ]
    result = vote_supplement_digits(reads)
    assert result.complete is True
    assert result.digits == "03921"
    assert result.frame_reads[0].digits == "03121"


def test_vote_rejects_ambiguous_position() -> None:
    reads = [
        SupplementFrameRead(0, "03121", 0.5),
        SupplementFrameRead(1, "03921", 0.5),
    ]
    result = vote_supplement_digits(reads, min_weight_share=0.55)
    assert result.complete is False
    assert result.digits == ""
