import pytest

from backend.app.chat.language import normalize_generated_script


@pytest.mark.parametrize(("language", "text", "expected"), [
    ("zh-Hans", "保單費用為US$25 [S1]。", "保单费用为US$25 [S1]。"),
    ("zh-Hant", "保单费用为US$25 [S1]。", "保單費用為US$25 [S1]。"),
])
def test_generated_prose_uses_the_requested_script(language, text, expected):
    assert normalize_generated_script(text, language) == expected


def test_verbatim_quotes_and_urls_keep_their_original_characters():
    evidence = '「保單費用」 “保單費用” "保單費用" https://example.invalid/保單'
    assert normalize_generated_script("保單費用 " + evidence, "zh-Hans") == "保单费用 " + evidence


def test_english_response_keeps_source_terms_unchanged():
    text = "The source term is 保單費用 [S1]."
    assert normalize_generated_script(text, "en") == text
