"""Prompt injection hardening for code chunks sent to LLMs.

Detects common injection patterns and wraps code in clear delimiters
to prevent malicious code from manipulating agent behavior.
"""
import re
import logging

logger = logging.getLogger(__name__)

# Patterns that may indicate prompt injection attempts in code
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?previous\s+(instructions|context|rules)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),
    re.compile(r"<\|?(system|im_start|endoftext)\|?>", re.IGNORECASE),
    re.compile(r"\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>", re.IGNORECASE),
    re.compile(r"disregard\s+(the\s+)?(above|prior|previous)", re.IGNORECASE),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
    re.compile(r"override\s+(system\s+)?prompt", re.IGNORECASE),
    re.compile(r"act\s+as\s+(if\s+)?(you\s+are|a\s+)", re.IGNORECASE),
]


def sanitize_code_chunk(content: str) -> str:
    """Sanitize a code chunk by detecting and flagging injection patterns.

    Returns the content with any detected injection patterns wrapped
    in warning markers.
    """
    warnings = []
    for pattern in INJECTION_PATTERNS:
        matches = pattern.findall(content)
        if matches:
            warnings.append(f"[INJECTION_WARNING: Pattern detected: {pattern.pattern}]")

    if warnings:
        logger.warning("Potential prompt injection detected: %s", "; ".join(warnings))
        # Prepend warning but preserve the content for analysis
        warning_header = "\n".join(warnings) + "\n"
        return warning_header + content

    return content


def wrap_code_with_delimiters(content: str, file_path: str) -> str:
    """Wrap code content in clear delimiters for LLM prompts."""
    sanitized = sanitize_code_chunk(content)
    return f"=== FILE: {file_path} ===\n{sanitized}\n=== END FILE ==="
