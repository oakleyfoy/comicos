from app.services.external_catalog.locg_browser_security import (
    _has_verification_text,
    is_security_verification_screen,
)


class _FakePage:
    def __init__(self, text: str, *, block_count: int = 1) -> None:
        self._text = text
        self._block_count = block_count

    def evaluate(self, _script: str) -> str:
        return self._text

    def locator(self, selector: str):
        return self

    def count(self) -> int:
        return self._block_count


def test_verification_text_markers() -> None:
    assert _has_verification_text("performing security verification for your browser")
    assert _has_verification_text("confirm you are not a bot")
    assert not _has_verification_text("new comics this week")


def test_list_page_missing_block_is_verification() -> None:
    page = _FakePage("welcome", block_count=0)
    assert is_security_verification_screen(page, for_list_page=True)


def test_detail_page_missing_block_without_markers_not_verification() -> None:
    page = _FakePage("absolute batman #21", block_count=0)
    assert not is_security_verification_screen(page, for_list_page=False)
