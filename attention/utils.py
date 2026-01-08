import re
from datetime import date


_WHITESPACE_RE = re.compile(r"\s+")


def normalize_header(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def clean_text(text: str) -> str:
    if text is None:
        return ""
    value = text.replace("\u00a0", " ").replace("\u3000", " ")
    value = value.replace("\r", " ").replace("\t", " ")
    value = value.replace("\n", " ")
    value = _WHITESPACE_RE.sub(" ", value)
    return value.strip()


def clean_cell(value: str) -> str:
    if value is None:
        return ""
    text = value.strip()
    if text.startswith('="') and text.endswith('"'):
        text = text[2:-1]
    return clean_text(text)


def parse_roc_date(value: str) -> date:
    if value is None:
        raise ValueError("Missing date value")
    text = clean_text(value)
    text = text.replace(".", "/")
    parts = [p for p in text.split("/") if p]
    if len(parts) != 3:
        raise ValueError(f"Unexpected ROC date format: {value}")
    roc_year = int(parts[0])
    year = roc_year + 1911
    month = int(parts[1])
    day = int(parts[2])
    return date(year, month, day)


def format_date(value: date) -> str:
    return value.strftime("%Y-%m-%d")


def split_codes(raw: str) -> list[str]:
    if not raw:
        return []
    tokens = re.split(r"[\s,]+", raw.strip())
    return [t for t in tokens if t]


def is_warrant(code: str) -> bool:
    """
    Check if a stock code is a warrant (权证).
    Warrants typically have 5 or more digits, while regular stocks have 4 digits.
    
    Args:
        code: Stock code string
        
    Returns:
        True if the code is a warrant, False otherwise
    """
    if not code:
        return False
    # Remove any non-digit characters
    digits = ''.join(c for c in code if c.isdigit())
    # Warrants have 5 or more digits
    return len(digits) >= 5
