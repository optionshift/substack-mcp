import re
from dataclasses import dataclass, asdict


BANNED_WORDS = [
    "leverage", "synergy", "ensure", "revolutionary", "crucial",
    "delve", "foster", "comprehensive", "however", "essentially",
    "literally", "basically", "really", "very", "underscore",
    "showcase", "tapestry", "landscape", "multifaceted", "myriad",
    "plethora", "pivotal", "intricate", "realm", "simply",
]

# AI-tell patterns from the article-social-launch skill rubric, plus
# common LLM giveaways. Case-insensitive, matched as substring/phrase.
AI_PATTERNS = [
    r"not because [^.]*?\. ?because",
    r"here'?s the thing",
    r"here'?s what nobody tells you",
    r"the real [^.]*? isn'?t",
    r"that'?s not [^.]*?\. ?that'?s",
    r"let that sink in",
    r"read that again",
    r"full stop\.",
    r"unpopular opinion[:\b]",
    r"hot take[:\b]",
    r"nobody is talking about",
]


@dataclass
class Violation:
    rule: str
    message: str
    severity: str  # "hard" | "soft"
    span: tuple[int, int] | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if d["span"] is not None:
            d["span"] = list(d["span"])
        return d


# Label pattern: line starts with a short label (1-4 words, <=30 chars) then ': value'.
# This matches things like "Compensation to creators: zero." but NOT
# "here is the thing about creators: they are not employees".


def _is_label_colon(text: str, colon_pos: int) -> bool:
    """True if the colon at `colon_pos` is part of a 'Word: value' label pattern."""
    line_start = text.rfind("\n", 0, colon_pos) + 1
    line_to_colon = text[line_start: colon_pos]
    after = text[colon_pos + 1: colon_pos + 3]
    if not after.startswith(" ") or not after[1:].strip():
        return False
    # Label must be 1-4 words, <=30 chars total, only word chars + spaces
    label = line_to_colon.strip()
    if not label or len(label) > 30:
        return False
    if not re.fullmatch(r"\w+(?:\s+\w+){0,3}", label):
        return False
    return True


def check(text: str | None) -> list[Violation]:
    """Return the list of voice violations in `text`. Empty list = clean."""
    if not text:
        return []

    violations: list[Violation] = []

    # Em dash
    for m in re.finditer(r"—", text):
        violations.append(Violation(
            rule="em_dash",
            message="Em dash banned. Use a period.",
            severity="hard",
            span=(m.start(), m.end()),
        ))

    # En dash used between words (not in date/number ranges like "2024–2025")
    for m in re.finditer(r"(?<=\w)\s*–\s*(?=\w)", text):
        local = text[max(0, m.start() - 4): m.end() + 4]
        if re.search(r"\d\s*–\s*\d", local):
            continue
        violations.append(Violation(
            rule="en_dash_used_as_em",
            message="En dash used as em dash banned. Use a period.",
            severity="hard",
            span=(m.start(), m.end()),
        ))

    # Semicolon
    for m in re.finditer(r";", text):
        violations.append(Violation(
            rule="semicolon",
            message="Semicolon banned. Use a period.",
            severity="hard",
            span=(m.start(), m.end()),
        ))

    # Colon — except in label pattern (short 'Word: value' at line start)
    for m in re.finditer(r":", text):
        if _is_label_colon(text, m.start()):
            continue
        violations.append(Violation(
            rule="colon",
            message="Colon banned outside 'Word: value' label pattern. Use a period.",
            severity="hard",
            span=(m.start(), m.end()),
        ))

    # Banned words (whole-word, case insensitive)
    lower = text.lower()
    for word in BANNED_WORDS:
        for m in re.finditer(rf"\b{re.escape(word)}\b", lower):
            violations.append(Violation(
                rule="banned_word",
                message=f"Banned word '{word}'.",
                severity="hard",
                span=(m.start(), m.end()),
            ))

    # AI patterns
    for pat in AI_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            violations.append(Violation(
                rule="ai_pattern",
                message=f"AI-tell phrase matched: '{m.group(0)}'",
                severity="hard",
                span=(m.start(), m.end()),
            ))

    return violations
