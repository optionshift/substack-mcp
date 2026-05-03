import pytest

from src.voice_check import check, Violation


class TestVoiceCheck:
    def test_clean_text_passes(self):
        assert check("two years ago i wouldn't know an API from a CLI") == []

    def test_em_dash_blocks(self):
        violations = check("the answer — wait — is no")
        assert any(v.rule == "em_dash" for v in violations)

    def test_en_dash_between_words_blocks(self):
        violations = check("the answer – wait – is no")
        assert any(v.rule == "en_dash_used_as_em" for v in violations)

    def test_semicolon_blocks(self):
        violations = check("we shipped it; nobody noticed")
        assert any(v.rule == "semicolon" for v in violations)

    def test_label_colon_passes(self):
        # 'Word: value' label pattern is the explicit exception per voice rules
        assert check("Compensation to creators: zero.") == []

    def test_inline_colon_blocks(self):
        violations = check("here is the thing about creators: they are not employees")
        # this should hit either ai_pattern (here's the thing variant) or colon — either is fine
        assert any(v.rule in ("colon", "ai_pattern") for v in violations)

    def test_banned_word_leverage(self):
        violations = check("we can leverage this for distribution")
        assert any(v.rule == "banned_word" and "leverage" in v.message for v in violations)

    def test_banned_word_revolutionary(self):
        violations = check("this is a revolutionary product")
        assert any(v.rule == "banned_word" and "revolutionary" in v.message for v in violations)

    def test_ai_pattern_not_because(self):
        violations = check("we shipped not because we had to. because we wanted to.")
        assert any(v.rule == "ai_pattern" and "not because" in v.message.lower() for v in violations)

    def test_ai_pattern_heres_the_thing(self):
        violations = check("here's the thing about distribution")
        assert any(v.rule == "ai_pattern" for v in violations)

    def test_ai_pattern_let_that_sink_in(self):
        violations = check("ten thousand creators. let that sink in.")
        assert any(v.rule == "ai_pattern" for v in violations)

    def test_violation_to_dict(self):
        violations = check("we leverage synergy")
        assert len(violations) >= 1
        d = violations[0].to_dict()
        assert "rule" in d and "message" in d and "severity" in d

    def test_empty_string_passes(self):
        assert check("") == []

    def test_none_passes(self):
        # check(None) should not crash; allow either empty list or graceful behavior
        assert check(None) == [] or check(None) is not None
