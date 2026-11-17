"""Self-checks for vision-OCR reply sanitation.

Run: uv run python backend/test_ocr_clean.py
"""

from services import _clean_ocr_text


def test_plain_word_passes_through():
    assert _clean_ocr_text("kitten") == "kitten"


def test_punctuation_and_quotes_are_removed():
    assert _clean_ocr_text("“Mop.”") == "mop"
    assert _clean_ocr_text("thumb,") == "thumb"


def test_sentinel_and_refusals_mean_illegible():
    assert _clean_ocr_text("-") == ""
    assert _clean_ocr_text("None") == ""
    assert _clean_ocr_text("nothing.") == ""
    assert _clean_ocr_text("``") == ""


def test_conversational_lead_in_is_stripped():
    assert _clean_ocr_text("The word is: thumb") == "thumb"
    assert _clean_ocr_text("Answer — ship") == "ship"


def test_leading_article_is_dropped():
    assert _clean_ocr_text("the ship") == "ship"
    # A one-token answer that happens to be an article stays intact.
    assert _clean_ocr_text("a") == "a"


def test_reasoning_text_is_cut_to_one_word():
    raw = "We need answer only recognized word(s) lowercase no punctuation. Final: (empty)."
    assert len(_clean_ocr_text(raw).split()) == 1


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all OCR sanitation self-checks passed")
