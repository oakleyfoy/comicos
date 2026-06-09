from app.services.recognition.confidence_service import bucket_for_confidence, combine_confidence
from app.services.recognition.cover_matcher import score_cover_image
from app.services.recognition.ocr_matcher import extract_ocr_signal
from app.services.recognition.recognition_models import RecognitionCandidateRead, RecognitionIdentifyRead
from app.services.recognition.recognition_service import (
    identify_comic_cover,
    identify_comic_cover_read,
    list_recognition_candidates_read,
    recognition_metrics_snapshot,
)
from app.services.recognition.recognition_types import (
    RecognitionBucket,
    RecognitionCandidate,
    RecognitionImageSignal,
    RecognitionOCRSignal,
    RecognitionResult,
)

