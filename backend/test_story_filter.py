"""Self-checks for the story safety filter.

Run: uv run python backend/test_story_filter.py
"""

from exercises.exercise5 import _build_user_prompt, _filter_story


def test_blocked_word_removes_only_its_sentence():
    text = "Mia likes her cat. The bomb went off. Then they ate cake."
    out = _filter_story(text)
    assert "bomb" not in out.lower()
    assert "Mia likes her cat." in out
    assert "Then they ate cake." in out


def test_substring_is_not_a_match():
    # "skill", "warm", "award" and "toward" contain blocked words but are safe.
    text = "She has skill. The sun was warm. He won an award and walked toward home."
    assert _filter_story(text) == text


def test_guardian_topics_are_filtered():
    text = "They went to the circus. Later they read a book."
    out = _filter_story(text, ["circus"])
    assert "circus" not in out.lower()
    assert "Later they read a book." in out


def test_empty_guardian_terms_are_ignored():
    text = "A short, kind story."
    assert _filter_story(text, ["", "  ", "a"]) == text


def test_guardian_topics_reach_the_prompt():
    prompt = _build_user_prompt(["cat", "sun"], ["space"], ["clowns"])
    assert "clowns" in prompt
    assert "space" in prompt


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
    print("all story-filter self-checks passed")
