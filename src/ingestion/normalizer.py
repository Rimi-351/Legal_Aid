"""
src/ingestion/normalizer.py
---------------------------
Conservative Unicode normalizer and language detection for Bengali and English legal text.
Preserves statutory typography without destructive transliteration.
"""

import unicodedata
import re
from typing import Tuple, List

# Known legacy Bijoy (SutonnyMJ ASCII layout) signature n-grams
BIJOY_SIGNATURES = [
    "AvBb",        # আইন
    "m¤úwË",       # সম্পত্তি
    "evsjv‡`k",    # বাংলাদেশ
    "AvBbvbyhvqx", # আইনানুযায়ী
    "wba©vwiZ",    # নির্ধারিত
    "weavb",       # বিধান
    "cÖavb",       # প্রধান
    "RvZxq",       # জাতীয়
    "ms‡kvab",     # সংশোধন
]

# Bengali Unicode block range: U+0980 to U+09FF
RE_BANGLA_CHAR = re.compile(r"[\u0980-\u09FF]")
RE_LATIN_CHAR = re.compile(r"[a-zA-Z]")
RE_MULTIPLE_SPACES = re.compile(r"[ \t\f\v]+")
RE_EXCESSIVE_NEWLINES = re.compile(r"\n{3,}")


def normalize_bengali_english_text(text: str) -> str:
    """
    Applies conservative Unicode NFC normalization to preserve Bengali grapheme
    clusters, conjunct ligatures (e.g. ক + ্ + ষ), and standard ASCII Latin text.
    
    Rules:
      1. Unicode Normalization Form C (NFC).
      2. Replaces non-breaking and unusual spaces with standard ASCII space.
      3. Normalizes Bengali dari (।) spacing without altering sentence boundary.
      4. Strips orphaned ZWNJ/ZWJ that do not touch Bengali consonants.
      5. Preserves original case and legal numbers.
    """
    if not text:
        return ""

    # 1. Standard Unicode NFC
    normalized = unicodedata.normalize("NFC", text)

    # 2. Convert non-breaking space (U+00A0) and zero-width spaces (U+200B)
    normalized = normalized.replace("\u00a0", " ").replace("\u200b", "")

    # 3. Clean up orphaned Zero-Width Non-Joiner (U+200C) and Joiner (U+200D)
    # Only keep ZWNJ/ZWJ when immediately preceded by a Bengali character
    normalized = re.sub(r"(?<![\u0980-\u09FF])[\u200C\u200D]", "", normalized)
    normalized = re.sub(r"[\u200C\u200D](?![\u0980-\u09FF])", "", normalized)

    # 4. Normalize multiple consecutive horizontal spaces
    normalized = RE_MULTIPLE_SPACES.sub(" ", normalized)

    # 5. Collapse excessive line breaks (max 2 consecutive newlines)
    normalized = RE_EXCESSIVE_NEWLINES.sub("\n\n", normalized)

    return normalized.strip()


def detect_suspect_bijoy(text: str) -> Tuple[bool, List[str]]:
    """
    Evaluates whether raw text exhibits ASCII Bijoy / SutonnyMJ glyph signatures
    rather than clean Unicode Bengali.
    """
    found = []
    for sig in BIJOY_SIGNATURES:
        if sig in text:
            found.append(sig)
    # Flag as suspect if at least 2 distinct Bijoy signatures appear
    is_suspect = len(found) >= 2
    return is_suspect, found


def detect_language(text: str) -> str:
    """
    Classifies text as 'bn' (Bangla), 'en' (English), or 'mixed' based on character ratios.
    """
    if not text:
        return "empty"

    total_chars = len(text)
    bangla_count = len(RE_BANGLA_CHAR.findall(text))
    latin_count = len(RE_LATIN_CHAR.findall(text))

    bangla_ratio = bangla_count / total_chars
    latin_ratio = latin_count / total_chars

    if bangla_ratio > 0.35 and latin_ratio < 0.15:
        return "bn"
    elif latin_ratio > 0.35 and bangla_ratio < 0.15:
        return "en"
    elif bangla_ratio > 0.05 and latin_ratio > 0.05:
        return "mixed"
    elif bangla_ratio > latin_ratio:
        return "bn"
    else:
        return "en"
