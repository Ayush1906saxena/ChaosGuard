"""Sandbox-based fix validation with Docker container isolation.

Validates generated fixes by copying the clone directory, applying the fix,
and running language-specific compilation/testing commands inside ephemeral
Docker containers with strict resource and network isolation.

Falls back to host subprocess execution if Docker is not available.

See ADR-004 for the architectural rationale.
"""

import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

SANDBOX_TIMEOUT = 120  # seconds
SANDBOX_MEMORY_MB = 1024

# Language-to-Docker-image mapping for containerised validation.
DOCKER_IMAGES = {
    "python": "python:3.11-slim",
    "java": "maven:3.9-eclipse-temurin-21",
    "kotlin": "maven:3.9-eclipse-temurin-21",
    "javascript": "node:20-slim",
    "typescript": "node:20-slim",
}


def _docker_available() -> bool:
    """Return True if the Docker CLI is reachable and the daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


@dataclass
class ValidationResult:
    syntax_valid: bool = False
    compile_valid: bool = False
    tests_pass: bool = False
    error_output: str = ""


class SandboxValidator:
    """Validates fixes by compiling and testing in an isolated environment.

    When Docker is available, every validation step runs inside an ephemeral
    container with ``--network none``, ``--read-only``, memory/CPU limits, and
    a hard timeout.  If Docker is unavailable the validator falls back to
    running commands directly via ``subprocess.run()`` and logs a warning.
    """

    def __init__(self) -> None:
        self._use_docker = _docker_available()
        if not self._use_docker:
            logger.warning(
                "Docker is not available — fix validation will run directly "
                "on the host without container isolation. See ADR-004."
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(
        self,
        clone_path: str,
        file_path: str,
        fixed_content: str,
        language: str,
    ) -> ValidationResult:
        """Apply *fixed_content* to *file_path* in a copy of *clone_path* and
        run language-specific validation (syntax, compile, test).

        Returns a :class:`ValidationResult` describing what passed.
        """
        result = ValidationResult()

        if not clone_path or not os.path.isdir(clone_path):
            result.error_output = "Clone path not available for sandbox validation"
            return result

        tmp_dir = None
        try:
            # Copy the repository into a temporary directory.
            tmp_dir = tempfile.mkdtemp(prefix="chaosguard_sandbox_")
            shutil.copytree(
                clone_path,
                os.path.join(tmp_dir, "repo"),
                dirs_exist_ok=True,
            )
            repo_dir = os.path.join(tmp_dir, "repo")

            # Write the fixed file into the copy.
            fix_target = os.path.join(repo_dir, file_path)
            if not os.path.exists(fix_target):
                result.error_output = f"File not found in clone: {file_path}"
                return result

            with open(fix_target, "w", encoding="utf-8") as f:
                f.write(fixed_content)

            # Dispatch to the appropriate language validator.
            lang = language.lower()
            if lang in ("java", "kotlin"):
                result = self._validate_java(repo_dir, file_path, result)
            elif lang == "python":
                result = self._validate_python(repo_dir, file_path, result)
            elif lang in ("javascript", "typescript"):
                result = self._validate_js(repo_dir, file_path, lang, result)
            else:
                # For unsupported languages, just confirm the file is valid UTF-8.
                result.syntax_valid = True
                result.error_output = f"No validator for language: {language}"

        except Exception as exc:
            result.error_output = f"Sandbox validation error: {str(exc)}"
            logger.warning("Sandbox validation failed: %s", exc)
        finally:
            if tmp_dir and os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)

        return result

    # ------------------------------------------------------------------
    # Command execution helpers
    # ------------------------------------------------------------------

    def _run_cmd(
        self,
        cmd: list[str],
        cwd: str,
        language: str = "python",
    ) -> tuple[int, str]:
        """Run *cmd* inside a Docker container (preferred) or on the host.

        *cwd* is the workspace directory that will be bind-mounted into the
        container at ``/workspace``.  *language* selects the Docker image.
        """
        if self._use_docker:
            return self._run_in_docker(cmd, cwd, language)
        return self._run_on_host(cmd, cwd)

    def _run_in_docker(
        self,
        cmd: list[str],
        workspace: str,
        language: str,
    ) -> tuple[int, str]:
        """Execute *cmd* in an ephemeral Docker container.

        Container configuration:
        - ``--rm``              — auto-remove on exit.
        - ``--network none``    — no network access.
        - ``--read-only``       — immutable root filesystem.
        - ``--memory 1g``       — hard memory limit.
        - ``--cpus 1.0``        — CPU quota.
        - ``--stop-timeout 120``— hard kill after 120 s.
        - Workspace mounted rw at ``/workspace``.
        """
        image = DOCKER_IMAGES.get(language, "python:3.11-slim")

        docker_cmd = [
            "docker", "run",
            "--rm",
            "--network", "none",
            "--read-only",
            "--memory", "1g",
            "--cpus", "1.0",
            "--stop-timeout", "120",
            "-v", f"{workspace}:/workspace:rw",
            "-w", "/workspace",
            image,
        ] + cmd

        try:
            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=SANDBOX_TIMEOUT + 30,  # extra grace for container startup
            )
            output = (proc.stdout + "\n" + proc.stderr).strip()
            return proc.returncode, output[-2000:]
        except subprocess.TimeoutExpired:
            return -1, "Docker container timed out"
        except Exception as exc:
            logger.warning(
                "Docker execution failed, falling back to host: %s", exc
            )
            return self._run_on_host(cmd, workspace)

    def _run_on_host(
        self,
        cmd: list[str],
        cwd: str,
    ) -> tuple[int, str]:
        """Run *cmd* directly on the host as a subprocess (fallback)."""
        try:
            proc = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=SANDBOX_TIMEOUT,
                env={**os.environ, "MAVEN_OPTS": f"-Xmx{SANDBOX_MEMORY_MB}m"},
            )
            output = (proc.stdout + "\n" + proc.stderr).strip()
            return proc.returncode, output[-2000:]
        except subprocess.TimeoutExpired:
            return -1, "Command timed out"
        except FileNotFoundError:
            return -1, f"Command not found: {cmd[0]}"
        except Exception as exc:
            return -1, str(exc)

    # ------------------------------------------------------------------
    # Language-specific validators
    # ------------------------------------------------------------------

    def _validate_java(
        self,
        repo_dir: str,
        file_path: str,
        result: ValidationResult,
    ) -> ValidationResult:
        """Validate a Java/Kotlin fix using javac and Maven."""
        lang = "java"

        # Syntax check — compile the single file.
        rc, out = self._run_cmd(["javac", file_path], repo_dir, lang)
        result.syntax_valid = rc == 0
        if not result.syntax_valid:
            result.error_output = out
            return result

        # Full Maven compile (if pom.xml exists in the workspace).
        pom_path = os.path.join(repo_dir, "pom.xml")
        if os.path.exists(pom_path):
            rc, out = self._run_cmd(
                ["mvn", "compile", "-q", "-B"], repo_dir, lang,
            )
            result.compile_valid = rc == 0
            if not result.compile_valid:
                result.error_output = out
                return result

            # Maven test.
            rc, out = self._run_cmd(
                ["mvn", "test", "-q", "-B"], repo_dir, lang,
            )
            result.tests_pass = rc == 0
            if not result.tests_pass:
                result.error_output = out
        else:
            result.compile_valid = result.syntax_valid

        return result

    def _validate_python(
        self,
        repo_dir: str,
        file_path: str,
        result: ValidationResult,
    ) -> ValidationResult:
        """Validate a Python fix using py_compile and pytest."""
        lang = "python"

        # Syntax check.
        rc, out = self._run_cmd(
            ["python", "-m", "py_compile", file_path], repo_dir, lang,
        )
        result.syntax_valid = rc == 0
        if not result.syntax_valid:
            result.error_output = out
            return result

        result.compile_valid = True

        # Run pytest if the project appears to use it.
        test_markers = ("pytest.ini", "setup.py", "pyproject.toml")
        if any(os.path.exists(os.path.join(repo_dir, m)) for m in test_markers):
            rc, out = self._run_cmd(
                ["python", "-m", "pytest", "-q", "--tb=short", "-x"],
                repo_dir,
                lang,
            )
            result.tests_pass = rc == 0
            if not result.tests_pass:
                result.error_output = out

        return result

    def _validate_js(
        self,
        repo_dir: str,
        file_path: str,
        lang: str,
        result: ValidationResult,
    ) -> ValidationResult:
        """Validate a JavaScript or TypeScript fix."""
        if lang == "typescript":
            rc, out = self._run_cmd(
                ["npx", "tsc", "--noEmit"], repo_dir, lang,
            )
        else:
            rc, out = self._run_cmd(
                ["node", "--check", file_path], repo_dir, lang,
            )

        result.syntax_valid = rc == 0
        if not result.syntax_valid:
            result.error_output = out
            return result

        result.compile_valid = result.syntax_valid

        # Run npm test if package.json exists.
        if os.path.exists(os.path.join(repo_dir, "package.json")):
            rc, out = self._run_cmd(
                ["npm", "test", "--if-present"], repo_dir, lang,
            )
            result.tests_pass = rc == 0
            if not result.tests_pass:
                result.error_output = out

        return result
