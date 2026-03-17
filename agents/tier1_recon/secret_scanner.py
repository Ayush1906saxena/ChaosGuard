import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SecretPattern:
    name: str
    pattern: str
    severity: str = "high"
    description: str = ""
    compiled: re.Pattern = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.compiled = re.compile(self.pattern, re.IGNORECASE)


# ---------------------------------------------------------------------------
# 25 secret patterns
# ---------------------------------------------------------------------------
SECRET_PATTERNS: list[SecretPattern] = [
    SecretPattern(
        name="AWS Access Key ID",
        pattern=r"(?:^|['\"\s=])(?:AKIA[0-9A-Z]{16})(?:['\"\s]|$)",
        severity="critical",
        description="AWS Access Key ID found in source code",
    ),
    SecretPattern(
        name="AWS Secret Access Key",
        pattern=r"(?:aws_secret_access_key|aws_secret_key|secret_key)\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?",
        severity="critical",
        description="AWS Secret Access Key found in source code",
    ),
    SecretPattern(
        name="GitHub Token",
        pattern=r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,255}",
        severity="critical",
        description="GitHub personal access or OAuth token",
    ),
    SecretPattern(
        name="GitHub Fine-grained Token",
        pattern=r"github_pat_[A-Za-z0-9_]{22,255}",
        severity="critical",
        description="GitHub fine-grained personal access token",
    ),
    SecretPattern(
        name="Slack Token",
        pattern=r"xox[boaprs]-[0-9]{10,13}-[A-Za-z0-9-]{20,50}",
        severity="high",
        description="Slack bot, user, or app token",
    ),
    SecretPattern(
        name="Slack Webhook",
        pattern=r"https://hooks\.slack\.com/services/T[A-Z0-9]{8,}/B[A-Z0-9]{8,}/[A-Za-z0-9]{24}",
        severity="high",
        description="Slack incoming webhook URL",
    ),
    SecretPattern(
        name="Stripe Secret Key",
        pattern=r"sk_(?:live|test)_[A-Za-z0-9]{20,99}",
        severity="critical",
        description="Stripe secret API key",
    ),
    SecretPattern(
        name="Stripe Publishable Key",
        pattern=r"pk_(?:live|test)_[A-Za-z0-9]{20,99}",
        severity="medium",
        description="Stripe publishable key (lower risk but should not be in backend code)",
    ),
    SecretPattern(
        name="Google API Key",
        pattern=r"AIza[0-9A-Za-z_-]{35}",
        severity="high",
        description="Google API key",
    ),
    SecretPattern(
        name="Google OAuth Client Secret",
        pattern=r"(?:client_secret)\s*[:=]\s*['\"]([A-Za-z0-9_-]{24})['\"]",
        severity="high",
        description="Google OAuth client secret",
    ),
    SecretPattern(
        name="GCP Service Account Key",
        pattern=r'"type"\s*:\s*"service_account"',
        severity="critical",
        description="GCP service account JSON key file",
    ),
    SecretPattern(
        name="Private Key (PEM)",
        pattern=r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
        severity="critical",
        description="Private key in PEM format",
    ),
    SecretPattern(
        name="JWT Token",
        pattern=r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
        severity="high",
        description="JSON Web Token (may contain sensitive claims)",
    ),
    SecretPattern(
        name="Database URL",
        pattern=r"(?:mysql|postgres|postgresql|mongodb|redis|amqp)://[^\s'\"]{10,}",
        severity="high",
        description="Database connection string with potential credentials",
    ),
    SecretPattern(
        name="Generic Password Assignment",
        pattern=r"(?:password|passwd|pwd)\s*[:=]\s*['\"]([^'\"]{8,})['\"]",
        severity="high",
        description="Hardcoded password assignment",
    ),
    SecretPattern(
        name="Generic Secret Assignment",
        pattern=r"(?:secret|api_key|apikey|access_token|auth_token)\s*[:=]\s*['\"]([^'\"]{8,})['\"]",
        severity="high",
        description="Hardcoded secret or API key assignment",
    ),
    SecretPattern(
        name="Heroku API Key",
        pattern=r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        severity="medium",
        description="Possible Heroku API key (UUID format near auth context)",
    ),
    SecretPattern(
        name="Twilio API Key",
        pattern=r"SK[0-9a-fA-F]{32}",
        severity="high",
        description="Twilio API key",
    ),
    SecretPattern(
        name="SendGrid API Key",
        pattern=r"SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}",
        severity="high",
        description="SendGrid API key",
    ),
    SecretPattern(
        name="Mailgun API Key",
        pattern=r"key-[0-9a-zA-Z]{32}",
        severity="high",
        description="Mailgun API key",
    ),
    SecretPattern(
        name="Square Access Token",
        pattern=r"sq0atp-[0-9A-Za-z_-]{22}",
        severity="high",
        description="Square access token",
    ),
    SecretPattern(
        name="npm Token",
        pattern=r"(?:npm_)[A-Za-z0-9]{36}",
        severity="high",
        description="npm access token",
    ),
    SecretPattern(
        name="PyPI Token",
        pattern=r"pypi-[A-Za-z0-9_-]{50,}",
        severity="high",
        description="PyPI upload token",
    ),
    SecretPattern(
        name="Docker Hub Token",
        pattern=r"dckr_pat_[A-Za-z0-9_-]{20,}",
        severity="high",
        description="Docker Hub personal access token",
    ),
    SecretPattern(
        name="Azure Storage Key",
        pattern=r"DefaultEndpointsProtocol=https;AccountName=[^;]+;AccountKey=[A-Za-z0-9+/=]{60,}",
        severity="critical",
        description="Azure Storage connection string with key",
    ),
    SecretPattern(
        name="Telegram Bot Token",
        pattern=r"[0-9]{8,10}:[A-Za-z0-9_-]{35}",
        severity="high",
        description="Telegram Bot API token",
    ),
]

# Files that should never appear in a repo
SENSITIVE_FILES: list[str] = [
    ".env",
    ".env.local",
    ".env.production",
    ".env.staging",
    "credentials.json",
    "service-account.json",
    "serviceAccountKey.json",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    ".htpasswd",
    ".pgpass",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "docker-compose.override.yml",
    "wp-config.php",
    "shadow",
    "passwd",
]


def shannon_entropy(data: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not data:
        return 0.0
    freq: dict[str, int] = {}
    for ch in data:
        freq[ch] = freq.get(ch, 0) + 1
    length = len(data)
    return -sum(
        (count / length) * math.log2(count / length)
        for count in freq.values()
    )


def _redact_secret(value: str, visible_chars: int = 4) -> str:
    """Redact a secret value, keeping only first N chars visible."""
    if len(value) <= visible_chars:
        return "***"
    return value[:visible_chars] + "*" * min(len(value) - visible_chars, 20)


def _is_common_false_positive(match_text: str, pattern_name: str) -> bool:
    """Filter out known false positives."""
    lower = match_text.lower().strip()

    # Skip example / placeholder values
    placeholders = [
        "example", "your_", "xxx", "placeholder", "change_me",
        "todo", "fixme", "insert_", "replace_", "<your", "dummy",
        "test_key", "sample", "fake",
    ]
    for ph in placeholders:
        if ph in lower:
            return True

    # Heroku UUID pattern is too broad; require auth-related context
    if pattern_name == "Heroku API Key":
        return True  # Skip unless context confirms

    # Very short matches are likely false positives
    if len(match_text.strip("'\" \t")) < 8:
        return True

    return False


def scan_for_secrets(
    file_path: str,
    content: str,
    file_name: str = "",
) -> list[dict[str, Any]]:
    """Scan file content for hardcoded secrets.

    Args:
        file_path: Repository-relative path of the file.
        content: Full text content of the file.
        file_name: Basename of the file for sensitive-file checks.

    Returns:
        A list of finding dicts.
    """
    findings: list[dict[str, Any]] = []

    # --- Sensitive file detection ---
    base_name = file_name or file_path.rsplit("/", 1)[-1]
    if base_name in SENSITIVE_FILES:
        findings.append({
            "id": f"SECRET-FILE-{base_name}",
            "title": f"Sensitive file committed: {base_name}",
            "severity": "high",
            "category": "secret",
            "description": f"The file '{base_name}' should not be committed to version control.",
            "file_path": file_path,
            "line": 1,
            "evidence": f"File: {base_name}",
            "remediation": f"Remove '{base_name}' from the repository and add it to .gitignore.",
            "agent": "tier1_recon.secret_scanner",
            "tier": 1,
        })

    # --- Regex pattern matching ---
    lines = content.split("\n")
    for line_no, line in enumerate(lines, start=1):
        # Skip comment-only lines
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//"):
            continue

        for pat in SECRET_PATTERNS:
            for m in pat.compiled.finditer(line):
                match_text = m.group(0)
                if _is_common_false_positive(match_text, pat.name):
                    continue
                findings.append({
                    "id": f"SECRET-{pat.name.upper().replace(' ', '-')}-L{line_no}",
                    "title": pat.name,
                    "severity": pat.severity,
                    "category": "secret",
                    "description": pat.description,
                    "file_path": file_path,
                    "line": line_no,
                    "evidence": _redact_secret(match_text.strip()),
                    "remediation": (
                        f"Remove the hardcoded {pat.name.lower()} and use environment "
                        "variables or a secrets manager instead."
                    ),
                    "agent": "tier1_recon.secret_scanner",
                    "tier": 1,
                })

    # --- Entropy analysis on string literals ---
    string_pattern = re.compile(r"""['"]([\w/+=@:._-]{20,})['"]\s*""")
    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//"):
            continue
        for m in string_pattern.finditer(line):
            value = m.group(1)
            entropy = shannon_entropy(value)
            if entropy > 4.5 and len(value) >= 20:
                # Check not already flagged by regex patterns
                already_found = any(
                    f.get("line") == line_no and f.get("category") == "secret"
                    for f in findings
                )
                if not already_found and not _is_common_false_positive(value, "entropy"):
                    findings.append({
                        "id": f"SECRET-HIGH-ENTROPY-L{line_no}",
                        "title": "High-entropy string (possible secret)",
                        "severity": "medium",
                        "category": "secret",
                        "description": (
                            f"A string with high Shannon entropy ({entropy:.2f}) was found, "
                            "which may indicate a hardcoded secret."
                        ),
                        "file_path": file_path,
                        "line": line_no,
                        "evidence": _redact_secret(value),
                        "remediation": (
                            "Review this string and move it to an environment variable "
                            "or secrets manager if it is sensitive."
                        ),
                        "agent": "tier1_recon.secret_scanner",
                        "tier": 1,
                    })

    return findings
