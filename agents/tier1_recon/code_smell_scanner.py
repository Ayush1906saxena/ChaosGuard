import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SmellPattern:
    name: str
    pattern: str
    severity: str
    category: str
    description: str
    remediation: str
    compiled: re.Pattern = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.compiled = re.compile(self.pattern, re.IGNORECASE)


CODE_SMELL_PATTERNS: list[SmellPattern] = [
    # SQL injection via concatenation
    SmellPattern(
        name="SQL String Concatenation",
        pattern=r"""(?:execute|cursor\.execute|query|raw|rawQuery)\s*\(\s*['"f].*(?:\+\s*\w|\{.*\}|%\s*\()""",
        severity="high",
        category="injection",
        description="SQL query built via string concatenation or formatting, risking SQL injection.",
        remediation="Use parameterized queries or an ORM to prevent SQL injection.",
    ),
    SmellPattern(
        name="SQL Concatenation with Variables",
        pattern=r"""(?:SELECT|INSERT|UPDATE|DELETE|FROM|WHERE)\s+.*['"]\s*\+\s*\w""",
        severity="high",
        category="injection",
        description="SQL statement concatenated with a variable.",
        remediation="Use parameterized queries instead of string concatenation.",
    ),

    # Dangerous eval/exec
    SmellPattern(
        name="eval() Usage",
        pattern=r"\beval\s*\(",
        severity="high",
        category="code_execution",
        description="Use of eval() can execute arbitrary code.",
        remediation="Replace eval() with a safe alternative such as ast.literal_eval() or JSON parsing.",
    ),
    SmellPattern(
        name="exec() Usage",
        pattern=r"\bexec\s*\(",
        severity="high",
        category="code_execution",
        description="Use of exec() can execute arbitrary code.",
        remediation="Eliminate exec() calls. Use safe alternatives for dynamic behavior.",
    ),
    SmellPattern(
        name="subprocess Shell=True",
        pattern=r"subprocess\.\w+\s*\(.*shell\s*=\s*True",
        severity="high",
        category="code_execution",
        description="subprocess with shell=True is vulnerable to shell injection.",
        remediation="Use shell=False (default) and pass arguments as a list.",
    ),
    SmellPattern(
        name="os.system() Usage",
        pattern=r"os\.system\s*\(",
        severity="high",
        category="code_execution",
        description="os.system() is vulnerable to command injection.",
        remediation="Use subprocess.run() with shell=False instead.",
    ),

    # Hardcoded IPs and URLs
    SmellPattern(
        name="Hardcoded IP Address",
        pattern=r"""['"]\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}['"]""",
        severity="low",
        category="hardcoded_value",
        description="Hardcoded IP address found; may cause issues across environments.",
        remediation="Use configuration files or environment variables for IP addresses.",
    ),
    SmellPattern(
        name="Hardcoded HTTP URL",
        pattern=r"""['"]http://[a-zA-Z0-9._-]+(?::\d+)?(?:/[^'"]*)?['"]""",
        severity="medium",
        category="hardcoded_value",
        description="Hardcoded HTTP URL found (not HTTPS).",
        remediation="Use HTTPS and externalize URLs via configuration.",
    ),

    # Empty catch / exception swallowing
    SmellPattern(
        name="Empty Catch Block (Python)",
        pattern=r"except\s*(?:\w+)?\s*:\s*(?:pass|\.\.\.)\s*$",
        severity="medium",
        category="error_handling",
        description="Exception is caught but silently ignored.",
        remediation="Log the exception or handle it meaningfully instead of using pass.",
    ),
    SmellPattern(
        name="Empty Catch Block (Java/JS/TS)",
        pattern=r"catch\s*\([^)]*\)\s*\{\s*\}",
        severity="medium",
        category="error_handling",
        description="Exception is caught with an empty handler.",
        remediation="Log or handle the exception properly.",
    ),
    SmellPattern(
        name="Bare Except (Python)",
        pattern=r"except\s*:\s*$",
        severity="medium",
        category="error_handling",
        description="Bare except catches all exceptions including SystemExit and KeyboardInterrupt.",
        remediation="Catch specific exception types (e.g., except ValueError:).",
    ),

    # TODO / FIXME / HACK markers
    SmellPattern(
        name="TODO Comment",
        pattern=r"(?:#|//|/\*)\s*TODO\b",
        severity="info",
        category="maintainability",
        description="TODO comment indicates unfinished work.",
        remediation="Address the TODO item or create a tracking issue.",
    ),
    SmellPattern(
        name="FIXME Comment",
        pattern=r"(?:#|//|/\*)\s*FIXME\b",
        severity="low",
        category="maintainability",
        description="FIXME comment indicates known broken code.",
        remediation="Fix the issue described by the FIXME comment.",
    ),
    SmellPattern(
        name="HACK Comment",
        pattern=r"(?:#|//|/\*)\s*HACK\b",
        severity="low",
        category="maintainability",
        description="HACK comment indicates a workaround or fragile code.",
        remediation="Refactor the hack into a proper implementation.",
    ),

    # Insecure random
    SmellPattern(
        name="Insecure Random (Python)",
        pattern=r"\brandom\.\w+\s*\(",
        severity="medium",
        category="cryptography",
        description="random module is not cryptographically secure.",
        remediation="Use secrets module for security-sensitive random values.",
    ),
    SmellPattern(
        name="Insecure Random (Java)",
        pattern=r"new\s+Random\s*\(",
        severity="medium",
        category="cryptography",
        description="java.util.Random is not cryptographically secure.",
        remediation="Use java.security.SecureRandom for security-sensitive operations.",
    ),
    SmellPattern(
        name="Math.random() Usage",
        pattern=r"Math\.random\s*\(",
        severity="medium",
        category="cryptography",
        description="Math.random() is not cryptographically secure.",
        remediation="Use crypto.getRandomValues() or crypto.randomUUID() instead.",
    ),

    # Missing input validation indicators
    SmellPattern(
        name="Unvalidated Request Body",
        pattern=r"request\.body\s*\[",
        severity="medium",
        category="input_validation",
        description="Direct access to request body without apparent validation.",
        remediation="Validate and sanitize all user input before use.",
    ),
    SmellPattern(
        name="innerHTML Assignment",
        pattern=r"\.innerHTML\s*=",
        severity="high",
        category="injection",
        description="Direct innerHTML assignment risks XSS.",
        remediation="Use textContent or a sanitization library like DOMPurify.",
    ),
    SmellPattern(
        name="dangerouslySetInnerHTML",
        pattern=r"dangerouslySetInnerHTML",
        severity="high",
        category="injection",
        description="React dangerouslySetInnerHTML bypasses XSS protection.",
        remediation="Sanitize HTML with DOMPurify before using dangerouslySetInnerHTML.",
    ),
]


def scan_code_smells(
    file_path: str,
    content: str,
    file_name: str = "",
) -> list[dict[str, Any]]:
    """Scan source code for common code smells and anti-patterns.

    Args:
        file_path: Repo-relative file path.
        content: Full file content.
        file_name: Basename of the file (unused but kept for interface consistency).

    Returns:
        List of finding dicts.
    """
    findings: list[dict[str, Any]] = []
    lines = content.split("\n")

    # Skip minified files (very long single lines)
    if len(lines) < 3 and len(content) > 5000:
        return findings

    # Skip binary-looking content
    if "\x00" in content[:1024]:
        return findings

    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            continue

        for pattern in CODE_SMELL_PATTERNS:
            if pattern.compiled.search(stripped):
                # Dedup: don't re-flag the same pattern on the same line
                dup = any(
                    f.get("line") == line_no and f.get("title") == pattern.name
                    for f in findings
                )
                if dup:
                    continue

                findings.append({
                    "id": f"SMELL-{pattern.name.upper().replace(' ', '-').replace('(', '').replace(')', '')}-L{line_no}",
                    "title": pattern.name,
                    "severity": pattern.severity,
                    "category": pattern.category,
                    "description": pattern.description,
                    "file_path": file_path,
                    "line": line_no,
                    "evidence": stripped[:120],
                    "remediation": pattern.remediation,
                    "agent": "tier1_recon.code_smell_scanner",
                    "tier": 1,
                })

    return findings
