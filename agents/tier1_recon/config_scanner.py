import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dockerfile scanner
# ---------------------------------------------------------------------------

def scan_dockerfile(file_path: str, content: str) -> list[dict[str, Any]]:
    """Deterministic checks for Dockerfile best practices."""
    findings: list[dict[str, Any]] = []
    lines = content.split("\n")

    has_user = False
    has_healthcheck = False

    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Running as root
        if re.match(r"^USER\s+root", stripped, re.IGNORECASE):
            findings.append(_finding(
                "CFG-DOCKER-ROOT", "Container runs as root",
                "critical", file_path, line_no,
                "Containers should not run as root. Use a non-root USER.",
                stripped,
            ))

        if re.match(r"^USER\s+", stripped, re.IGNORECASE) and "root" not in stripped.lower():
            has_user = True

        if re.match(r"^HEALTHCHECK\s+", stripped, re.IGNORECASE):
            has_healthcheck = True

        # Using :latest tag
        if re.match(r"^FROM\s+\S+:latest", stripped, re.IGNORECASE):
            findings.append(_finding(
                "CFG-DOCKER-LATEST", "Base image uses :latest tag",
                "medium", file_path, line_no,
                "Pin the base image to a specific version for reproducibility.",
                stripped,
            ))

        # FROM without tag at all
        from_match = re.match(r"^FROM\s+(\S+)$", stripped, re.IGNORECASE)
        if from_match and ":" not in from_match.group(1) and "scratch" not in from_match.group(1):
            findings.append(_finding(
                "CFG-DOCKER-NOTAG", "Base image has no version tag",
                "medium", file_path, line_no,
                "Always specify a version tag for the base image.",
                stripped,
            ))

        # ADD instead of COPY
        if re.match(r"^ADD\s+", stripped, re.IGNORECASE) and "http" not in stripped.lower():
            findings.append(_finding(
                "CFG-DOCKER-ADD", "Using ADD instead of COPY",
                "low", file_path, line_no,
                "Use COPY unless you need ADD's tar extraction or URL features.",
                stripped,
            ))

        # Secrets in ENV
        if re.match(r"^ENV\s+", stripped, re.IGNORECASE):
            env_lower = stripped.lower()
            if any(k in env_lower for k in ("password", "secret", "api_key", "token", "credential")):
                findings.append(_finding(
                    "CFG-DOCKER-ENV-SECRET", "Secret value in ENV instruction",
                    "high", file_path, line_no,
                    "Do not embed secrets in Dockerfile ENV. Use runtime secrets instead.",
                    stripped[:80],
                ))

        # EXPOSE on privileged ports
        expose_match = re.match(r"^EXPOSE\s+(\d+)", stripped, re.IGNORECASE)
        if expose_match:
            port = int(expose_match.group(1))
            if port < 1024 and port not in (80, 443, 8080, 8443):
                findings.append(_finding(
                    "CFG-DOCKER-PRIV-PORT", f"Exposing privileged port {port}",
                    "medium", file_path, line_no,
                    "Avoid exposing privileged ports unless necessary.",
                    stripped,
                ))

    if not has_user:
        findings.append(_finding(
            "CFG-DOCKER-NO-USER", "No USER instruction in Dockerfile",
            "high", file_path, 1,
            "Add a USER instruction to run the container as a non-root user.",
            "Dockerfile missing USER directive",
        ))

    if not has_healthcheck:
        findings.append(_finding(
            "CFG-DOCKER-NO-HEALTH", "No HEALTHCHECK instruction",
            "low", file_path, 1,
            "Add a HEALTHCHECK to enable container health monitoring.",
            "Dockerfile missing HEALTHCHECK directive",
        ))

    return findings


# ---------------------------------------------------------------------------
# docker-compose scanner
# ---------------------------------------------------------------------------

def scan_docker_compose(file_path: str, content: str) -> list[dict[str, Any]]:
    """Deterministic checks for docker-compose.yml."""
    findings: list[dict[str, Any]] = []
    lines = content.split("\n")

    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()

        if "privileged: true" in stripped:
            findings.append(_finding(
                "CFG-COMPOSE-PRIV", "Service running in privileged mode",
                "critical", file_path, line_no,
                "Remove 'privileged: true' unless absolutely required.",
                stripped,
            ))

        if "network_mode: host" in stripped:
            findings.append(_finding(
                "CFG-COMPOSE-HOST-NET", "Service using host network mode",
                "high", file_path, line_no,
                "Avoid host network mode; use bridge networking with explicit port mapping.",
                stripped,
            ))

        if re.search(r"ports:\s*$", stripped) or re.match(r"^\s*-\s*['\"]?0\.0\.0\.0:", stripped):
            if "0.0.0.0" in stripped:
                findings.append(_finding(
                    "CFG-COMPOSE-BIND-ALL", "Port bound to 0.0.0.0",
                    "medium", file_path, line_no,
                    "Bind ports to 127.0.0.1 in development to avoid network exposure.",
                    stripped,
                ))

        if "cap_add:" in stripped:
            findings.append(_finding(
                "CFG-COMPOSE-CAPS", "Additional Linux capabilities granted",
                "medium", file_path, line_no,
                "Review whether additional capabilities are necessary. Prefer cap_drop: ALL.",
                stripped,
            ))

    return findings


# ---------------------------------------------------------------------------
# Kubernetes manifest scanner
# ---------------------------------------------------------------------------

def scan_kubernetes(file_path: str, content: str) -> list[dict[str, Any]]:
    """Deterministic checks for Kubernetes YAML manifests."""
    findings: list[dict[str, Any]] = []
    lines = content.split("\n")

    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()

        if "privileged: true" in stripped:
            findings.append(_finding(
                "CFG-K8S-PRIV", "Container running in privileged mode",
                "critical", file_path, line_no,
                "Remove 'privileged: true' from securityContext.",
                stripped,
            ))

        if "runAsRoot: true" in stripped or "runAsUser: 0" in stripped:
            findings.append(_finding(
                "CFG-K8S-ROOT", "Container configured to run as root",
                "critical", file_path, line_no,
                "Set runAsNonRoot: true and specify a non-zero runAsUser.",
                stripped,
            ))

        if "readOnlyRootFilesystem: false" in stripped:
            findings.append(_finding(
                "CFG-K8S-RW-FS", "Root filesystem is writable",
                "medium", file_path, line_no,
                "Set readOnlyRootFilesystem: true and use emptyDir for writable paths.",
                stripped,
            ))

        if "hostNetwork: true" in stripped:
            findings.append(_finding(
                "CFG-K8S-HOST-NET", "Pod using host network",
                "high", file_path, line_no,
                "Avoid hostNetwork unless required for network-level pods.",
                stripped,
            ))

        if "hostPID: true" in stripped:
            findings.append(_finding(
                "CFG-K8S-HOST-PID", "Pod sharing host PID namespace",
                "high", file_path, line_no,
                "Remove hostPID: true to isolate process namespaces.",
                stripped,
            ))

        if re.search(r"allowPrivilegeEscalation:\s*true", stripped):
            findings.append(_finding(
                "CFG-K8S-PRIV-ESC", "Privilege escalation allowed",
                "high", file_path, line_no,
                "Set allowPrivilegeEscalation: false.",
                stripped,
            ))

        # Missing resource limits (heuristic: container spec without limits)
        if "resources:" in stripped:
            # Look ahead a few lines for limits
            has_limits = any(
                "limits:" in lines[i].strip()
                for i in range(line_no, min(line_no + 5, len(lines)))
            )
            if not has_limits:
                findings.append(_finding(
                    "CFG-K8S-NO-LIMITS", "Container missing resource limits",
                    "medium", file_path, line_no,
                    "Define CPU and memory limits to prevent resource exhaustion.",
                    stripped,
                ))

    return findings


# ---------------------------------------------------------------------------
# CI/CD config scanner
# ---------------------------------------------------------------------------

def scan_cicd(file_path: str, content: str) -> list[dict[str, Any]]:
    """Deterministic checks for CI/CD configuration files."""
    findings: list[dict[str, Any]] = []
    lines = content.split("\n")

    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Hardcoded secrets in CI
        if re.search(r"(password|secret|token|api_key)\s*[:=]\s*['\"][^'\"$]+['\"]", stripped, re.IGNORECASE):
            if "${{" not in stripped and "${" not in stripped:
                findings.append(_finding(
                    "CFG-CI-HARDCODED-SECRET", "Hardcoded secret in CI/CD config",
                    "critical", file_path, line_no,
                    "Use CI/CD secret variables instead of hardcoded values.",
                    stripped[:80],
                ))

        # Curl piped to shell
        if re.search(r"curl\s.*\|\s*(bash|sh|zsh)", stripped):
            findings.append(_finding(
                "CFG-CI-CURL-PIPE", "curl piped directly to shell",
                "high", file_path, line_no,
                "Download scripts to a file, verify integrity, then execute.",
                stripped[:80],
            ))

        # Unpinned actions (GitHub Actions)
        action_match = re.match(r"^\s*-?\s*uses:\s+([^@]+)@(.+)", stripped)
        if action_match:
            ref = action_match.group(2).strip()
            if ref in ("master", "main", "latest"):
                findings.append(_finding(
                    "CFG-CI-UNPINNED-ACTION", f"Unpinned GitHub Action: {action_match.group(1)}",
                    "medium", file_path, line_no,
                    "Pin GitHub Actions to a specific commit SHA or version tag.",
                    stripped,
                ))

    return findings


# ---------------------------------------------------------------------------
# Application config scanner (generic YAML/JSON/properties)
# ---------------------------------------------------------------------------

def scan_app_config(file_path: str, content: str) -> list[dict[str, Any]]:
    """Scan application config files for insecure settings."""
    findings: list[dict[str, Any]] = []
    lines = content.split("\n")
    lower_content = content.lower()

    # Debug mode
    if re.search(r"debug\s*[:=]\s*true", lower_content):
        for line_no, line in enumerate(lines, start=1):
            if re.search(r"debug\s*[:=]\s*true", line.lower()):
                findings.append(_finding(
                    "CFG-APP-DEBUG", "Debug mode enabled",
                    "high", file_path, line_no,
                    "Disable debug mode in production configurations.",
                    line.strip(),
                ))
                break

    # Insecure SSL/TLS settings
    if re.search(r"(ssl_verify|verify_ssl|tls_verify)\s*[:=]\s*(false|0)", lower_content):
        for line_no, line in enumerate(lines, start=1):
            if re.search(r"(ssl_verify|verify_ssl|tls_verify)\s*[:=]\s*(false|0)", line.lower()):
                findings.append(_finding(
                    "CFG-APP-SSL-DISABLED", "SSL/TLS verification disabled",
                    "critical", file_path, line_no,
                    "Enable SSL/TLS verification to prevent MITM attacks.",
                    line.strip(),
                ))

    # CORS wildcard
    if re.search(r"(cors|allowed_origins|allow_origin)\s*[:=]\s*['\"]?\*", lower_content):
        for line_no, line in enumerate(lines, start=1):
            if re.search(r"(cors|allowed_origins|allow_origin)\s*[:=]\s*['\"]?\*", line.lower()):
                findings.append(_finding(
                    "CFG-APP-CORS-WILDCARD", "CORS allows all origins",
                    "high", file_path, line_no,
                    "Restrict CORS to specific trusted origins.",
                    line.strip(),
                ))

    return findings


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

# Routing table: basename -> scanner function
_SCANNER_ROUTES: dict[str, Any] = {}


def _route_file(file_path: str, file_name: str) -> Any | None:
    """Determine the appropriate scanner for a file."""
    name_lower = file_name.lower()

    if name_lower == "dockerfile" or name_lower.startswith("dockerfile."):
        return scan_dockerfile
    if name_lower in ("docker-compose.yml", "docker-compose.yaml",
                       "compose.yml", "compose.yaml"):
        return scan_docker_compose
    if name_lower.endswith((".yml", ".yaml")):
        # Could be K8s or CI/CD
        content_hint_k8s = ("apiVersion", "kind:", "metadata:")
        content_hint_ci = ("jobs:", "steps:", "pipeline:", "stages:")
        # Return None; caller will detect from content
        return None
    if name_lower in ("application.yml", "application.yaml", "application.properties",
                       "appsettings.json", "config.json", "config.yml", "config.yaml",
                       ".env.example"):
        return scan_app_config

    return None


def scan_configs(
    file_path: str,
    content: str,
    file_name: str = "",
) -> list[dict[str, Any]]:
    """Route a file to the appropriate config scanner(s).

    Args:
        file_path: Repo-relative path.
        content: Full text content.
        file_name: Basename of the file.

    Returns:
        List of finding dicts.
    """
    base_name = file_name or file_path.rsplit("/", 1)[-1]
    scanner = _route_file(file_path, base_name)

    if scanner is not None:
        return scanner(file_path, content)

    # For generic YAML files, try to auto-detect type from content
    name_lower = base_name.lower()
    if name_lower.endswith((".yml", ".yaml")):
        findings: list[dict[str, Any]] = []

        # Check if it looks like Kubernetes
        if "apiVersion:" in content and "kind:" in content:
            findings.extend(scan_kubernetes(file_path, content))

        # Check if it looks like CI/CD
        ci_path_hints = (".github/workflows", ".gitlab-ci", "azure-pipelines",
                         ".circleci", "Jenkinsfile", "bitbucket-pipelines")
        if any(hint in file_path for hint in ci_path_hints):
            findings.extend(scan_cicd(file_path, content))
        elif "jobs:" in content and ("steps:" in content or "runs-on:" in content):
            findings.extend(scan_cicd(file_path, content))

        if not findings:
            # Generic app config scan
            findings.extend(scan_app_config(file_path, content))

        return findings

    # JSON config files
    if name_lower.endswith(".json"):
        return scan_app_config(file_path, content)

    return []


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _finding(
    finding_id: str,
    title: str,
    severity: str,
    file_path: str,
    line: int,
    remediation: str,
    evidence: str,
) -> dict[str, Any]:
    return {
        "id": finding_id,
        "title": title,
        "severity": severity,
        "category": "configuration",
        "description": title,
        "file_path": file_path,
        "line": line,
        "evidence": evidence,
        "remediation": remediation,
        "agent": "tier1_recon.config_scanner",
        "tier": 1,
    }
