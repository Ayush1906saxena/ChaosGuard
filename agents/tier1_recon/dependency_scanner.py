import logging
import re
import xml.etree.ElementTree as ET
from typing import Any, Optional

import psycopg2

from config import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Build-file parsers
# ---------------------------------------------------------------------------

def parse_pom_xml(content: str) -> list[dict[str, str]]:
    """Parse Maven pom.xml and extract dependencies."""
    deps: list[dict[str, str]] = []
    try:
        root = ET.fromstring(content)
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}
        # Try with namespace first, then without
        for dep_elem in root.findall(".//m:dependency", ns) or root.findall(".//dependency"):
            group = dep_elem.findtext("m:groupId", "", ns) or dep_elem.findtext("groupId", "")
            artifact = dep_elem.findtext("m:artifactId", "", ns) or dep_elem.findtext("artifactId", "")
            version = dep_elem.findtext("m:version", "", ns) or dep_elem.findtext("version", "")
            if group and artifact:
                deps.append({
                    "ecosystem": "maven",
                    "name": f"{group}:{artifact}",
                    "version": version,
                })
    except ET.ParseError as exc:
        logger.warning("Failed to parse pom.xml: %s", exc)
    return deps


def parse_package_json(content: str) -> list[dict[str, str]]:
    """Parse npm package.json and extract dependencies."""
    import json
    deps: list[dict[str, str]] = []
    try:
        data = json.loads(content)
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            for name, version in data.get(section, {}).items():
                # Strip leading ^ ~ >= etc.
                clean_version = re.sub(r"^[\^~>=<\s]+", "", version)
                deps.append({
                    "ecosystem": "npm",
                    "name": name,
                    "version": clean_version,
                })
    except (json.JSONDecodeError, AttributeError) as exc:
        logger.warning("Failed to parse package.json: %s", exc)
    return deps


def parse_requirements_txt(content: str) -> list[dict[str, str]]:
    """Parse Python requirements.txt."""
    deps: list[dict[str, str]] = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Handle name==version, name>=version, name~=version
        match = re.match(r"([A-Za-z0-9_.-]+)\s*(?:[=~!<>]+)\s*([A-Za-z0-9._-]+)", line)
        if match:
            deps.append({
                "ecosystem": "pypi",
                "name": match.group(1).lower(),
                "version": match.group(2),
            })
        else:
            # Unpinned dependency
            name_match = re.match(r"([A-Za-z0-9_.-]+)", line)
            if name_match:
                deps.append({
                    "ecosystem": "pypi",
                    "name": name_match.group(1).lower(),
                    "version": "",
                })
    return deps


def parse_go_mod(content: str) -> list[dict[str, str]]:
    """Parse Go go.mod file."""
    deps: list[dict[str, str]] = []
    in_require = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("require ("):
            in_require = True
            continue
        if stripped == ")" and in_require:
            in_require = False
            continue
        if in_require or stripped.startswith("require "):
            parts = stripped.replace("require ", "").strip().split()
            if len(parts) >= 2:
                module = parts[0]
                version = parts[1].lstrip("v")
                deps.append({
                    "ecosystem": "go",
                    "name": module,
                    "version": version,
                })
    return deps


# Map file basenames to their parser functions
BUILD_FILE_PARSERS: dict[str, Any] = {
    "pom.xml": parse_pom_xml,
    "package.json": parse_package_json,
    "requirements.txt": parse_requirements_txt,
    "go.mod": parse_go_mod,
    "Pipfile": parse_requirements_txt,  # Close enough for version extraction
    "setup.cfg": parse_requirements_txt,
}


def _version_in_range(
    dep_version: str,
    vuln_min: Optional[str],
    vuln_max: Optional[str],
) -> bool:
    """Check if dep_version falls within [vuln_min, vuln_max].

    Uses packaging.version for proper semver comparison with a string
    fallback for edge cases.
    """
    if not dep_version:
        return True  # Assume vulnerable if unpinned

    try:
        from packaging.version import Version
        v = Version(dep_version)
        if vuln_min and v < Version(vuln_min):
            return False
        if vuln_max and v > Version(vuln_max):
            return False
        return True
    except Exception:
        # Fallback: naive string comparison
        if vuln_min and dep_version < vuln_min:
            return False
        if vuln_max and dep_version > vuln_max:
            return False
        return True


def scan_dependencies(
    file_path: str,
    content: str,
    file_name: str = "",
) -> list[dict[str, Any]]:
    """Scan a dependency manifest for known vulnerabilities.

    Queries the CVE database in PostgreSQL for matching advisories.

    Args:
        file_path: Repo-relative path to the manifest file.
        content: Full text of the manifest.
        file_name: Basename of the file.

    Returns:
        List of finding dicts for vulnerable dependencies.
    """
    base_name = file_name or file_path.rsplit("/", 1)[-1]
    parser = BUILD_FILE_PARSERS.get(base_name)
    if parser is None:
        return []

    deps = parser(content)
    if not deps:
        return []

    findings: list[dict[str, Any]] = []

    try:
        conn = psycopg2.connect(config.POSTGRES_DSN)
        try:
            with conn.cursor() as cur:
                for dep in deps:
                    cur.execute(
                        """
                        SELECT cve_id, severity, description,
                               affected_version_start, affected_version_end,
                               patched_version
                        FROM cve_entries
                        WHERE ecosystem = %s
                          AND package_name = %s
                        """,
                        (dep["ecosystem"], dep["name"]),
                    )
                    for row in cur.fetchall():
                        cve_id, sev, desc, v_start, v_end, patched = row
                        if _version_in_range(dep["version"], v_start, v_end):
                            findings.append({
                                "id": f"DEP-{cve_id}-{dep['name']}",
                                "title": f"Vulnerable dependency: {dep['name']} ({cve_id})",
                                "severity": sev or "high",
                                "category": "dependency",
                                "description": desc or f"{dep['name']} is affected by {cve_id}.",
                                "file_path": file_path,
                                "line": 1,
                                "evidence": (
                                    f"Package: {dep['name']}@{dep['version'] or 'unpinned'} | "
                                    f"CVE: {cve_id} | "
                                    f"Affected: {v_start or '*'} - {v_end or '*'}"
                                ),
                                "remediation": (
                                    f"Upgrade {dep['name']} to version {patched}."
                                    if patched
                                    else f"Review {cve_id} and apply the recommended fix."
                                ),
                                "agent": "tier1_recon.dependency_scanner",
                                "tier": 1,
                            })
        finally:
            conn.close()
    except psycopg2.Error as exc:
        logger.error("Database error during dependency scan: %s", exc)
        # Return what we can without the DB
        for dep in deps:
            if not dep["version"]:
                findings.append({
                    "id": f"DEP-UNPINNED-{dep['name']}",
                    "title": f"Unpinned dependency: {dep['name']}",
                    "severity": "low",
                    "category": "dependency",
                    "description": f"Dependency {dep['name']} has no pinned version.",
                    "file_path": file_path,
                    "line": 1,
                    "evidence": f"Package: {dep['name']} (no version specified)",
                    "remediation": f"Pin {dep['name']} to a specific, known-good version.",
                    "agent": "tier1_recon.dependency_scanner",
                    "tier": 1,
                })

    return findings
