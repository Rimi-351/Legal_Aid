"""
src/rag - Legal RAG pipeline with strict citation validation and local LLM execution.
"""
from .config import settings
from .extractive import extractive_answer
from .llm_answer import generate_answer
from .citation_validator import validate, ValidationResult, ClaimValidationResult

__all__ = [
    "settings",
    "extractive_answer",
    "generate_answer",
    "validate",
    "ValidationResult",
    "ClaimValidationResult",
]

