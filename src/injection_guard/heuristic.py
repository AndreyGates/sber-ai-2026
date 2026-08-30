from __future__ import annotations

import re

# --- pattern categories ---

ROLE_OVERRIDE_PATTERNS_EN = [
    r"ignore\s+(all\s+)?(previous|prior)\s+(instructions|rules)",
    r"ignore\s+(all\s+)?rules",
    r"you\s+are\s+now\s+(?:a|an)\s+",
    r"act\s+as\s+(?:a|an)\s+",
    r"pretend\s+(to\s+be|you\s+are)",
    r"forget\s+(your\s+)?rules",
    r"forget\s+(all\s+)?(your\s+)?instructions",
    r"disregard\s+(all\s+)?(your\s+)?(previous\s+)?(instructions|rules)",
    r"override\s+(your\s+)?(previous\s+)?(instructions|rules)",
    r"new\s+instructions?\s*:",
    r"from\s+now\s+on\s+you\s+(are|will|must|should)",
    r"your\s+new\s+(role|persona|identity|instructions)",
]

ROLE_OVERRIDE_PATTERNS_RU = [
    r"забудь\s+(все\s+)?(предыдущие\s+)?инструкции",
    r"забудь\s+(свои\s+)?правила",
    r"игнорируй\s+(все\s+)?(предыдущие\s+)?(указания|инструкции)",
    r"представь\s+(что\s+ты|себя\s+как)",
    r"ты\s+теперь\s+",
    r"новые\s+инструкции\s*:",
    r"с\s+этого\s+момента\s+ты\s+",
]

SYSTEM_PROMPT_PATTERNS_EN = [
    r"system\s+prompt",
    r"reveal\s+your\s+instructions",
    r"show\s+your\s+(system\s+)?instructions",
    r"what\s+were\s+you\s+told\s+(to\s+do|not\s+to\s+do)",
    r"print\s+your\s+(system\s+)?prompt",
    r"output\s+your\s+(system\s+)?prompt",
    r"display\s+your\s+(system\s+)?instructions",
    r"repeat\s+your\s+(initial|system)\s+instructions",
    r"what\s+is\s+your\s+system\s+message",
]

SYSTEM_PROMPT_PATTERNS_RU = [
    r"системн(ый|ого|ому)\s+промпт",
    r"покажи\s+(свои\s+)?инструкции",
    r"раскрой\s+(свои\s+)?инструкции",
    r"какие\s+у\s+тебя\s+инструкции",
    r"повтори\s+(свои\s+)?(системные\s+)?инструкции",
]

OBFUSCATION_PATTERNS_EN = [
    r"(?:translate|convert|decode)\s+(the\s+following|text|message|instruction)",
    r"(?:repeat|echo)\s+(?:exactly|verbatim)\s*:",
    r"(?:base64|rot13|caesar)\s*(?:decode|encode|decrypt)",
    r"[A-Za-z0-9+/]{80,}={0,2}",
]

OBFUSCATION_PATTERNS_RU = [
    r"(?:переведи|декодируй|расшифруй)\s+(следующий\s+)?(текст|сообщение|инструкцию)",
    r"(?:повтори|воспроизведи)\s+(дословно|точно)\s*:",
]

CODE_CONTAINER_PATTERNS = [
    r'"""[\s\S]*?(?:ignore|forget|override|disregard|you\s+are|act\s+as)[\s\S]*?"""',
    r"```[\s\S]*?(?:ignore|forget|override|disregard|you\s+are|act\s+as)[\s\S]*?```",
    r"'''[\s\S]*?(?:ignore|forget|override|disregard|you\s+are|act\s+as)[\s\S]*?'''",
    r'"[^"]{50,}?(?:ignore|forget|override|disregard)[^"]*?"',
]

CATEGORY_ROLE_OVERRIDE = "role_override"
CATEGORY_SYSTEM_PROMPT = "system_prompt_extraction"
CATEGORY_OBFUSCATION = "obfuscation"
CATEGORY_CODE_CONTAINER = "code_container"

CATEGORY_LABELS: dict[str, str] = {
    CATEGORY_ROLE_OVERRIDE: "смена роли/инструкций",
    CATEGORY_SYSTEM_PROMPT: "извлечение системного промпта",
    CATEGORY_OBFUSCATION: "обфускация",
    CATEGORY_CODE_CONTAINER: "код-контейнер с инструктивным текстом",
}


def _compile(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


_ALL_PATTERNS: dict[str, list[re.Pattern]] = {
    CATEGORY_ROLE_OVERRIDE: _compile(ROLE_OVERRIDE_PATTERNS_EN + ROLE_OVERRIDE_PATTERNS_RU),
    CATEGORY_SYSTEM_PROMPT: _compile(SYSTEM_PROMPT_PATTERNS_EN + SYSTEM_PROMPT_PATTERNS_RU),
    CATEGORY_OBFUSCATION: _compile(OBFUSCATION_PATTERNS_EN + OBFUSCATION_PATTERNS_RU),
    CATEGORY_CODE_CONTAINER: _compile(CODE_CONTAINER_PATTERNS),
}


def detect_heuristic_flags(text: str) -> list[str]:
    flags: list[str] = []
    for category, patterns in _ALL_PATTERNS.items():
        for pat in patterns:
            if pat.search(text):
                flags.append(category)
                break
    return flags
