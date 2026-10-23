"""
src/generation/__init__.py
--------------------------
Module for legal answer generation and extractive baseline comparison.
"""

from .prompts import LEGAL_SYSTEM_PROMPT, build_user_prompt
from .extractive import ExtractiveBaselineGenerator
from .client import OllamaGenerationClient
from .rubric import GenerationRubricEvaluator

__all__ = [
    "LEGAL_SYSTEM_PROMPT",
    "build_user_prompt",
    "ExtractiveBaselineGenerator",
    "OllamaGenerationClient",
    "GenerationRubricEvaluator",
]
