"""Sandbox-based fix validation.

Validates generated fixes by copying the clone directory, applying the fix,
and running language-specific compilation/testing commands in an isolated
subprocess with timeout and memory limits.
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


@dataclass
class ValidationResult:
    syntax_valid: bool = False
    compile_valid: bool = False
    tests_pass: bool = False
    error_output: str = ""


class SandboxValidator:
    """Validates fixes by compiling and testing in an isolated temp directory."""

    def validate(
        self,
        clone_path: str,
        file_path: str,
        fixed_content: str,
        language: str,
    ) -> ValidationResult:
        """Apply fix to a temp copy of the repo and run validation."""
        result = ValidationResult()

        if not clone_path or not os.path.isdir(clone_path):
            result.error_output = "Clone path not available for sandbox validation"
            return result

        tmp_dir = None
        try:
            # Copy clone to temp dir
            tmp_dir = tempfile.mkdtemp(prefix="chaosguard_sandbox_")
            shutil.copytree(clone_path, os.path.join(tmp_dir, "repo"), dirs_exist_ok=True)
            repo_dir = os.path.join(tmp_dir, "repo")

            # Apply fix
            fix_target = os.path.join(repo_dir, file_path)
            if not os.path.exists(fix_target):
                result.error_output = f"File not found in clone: {file_path}"
                return result

            with open(fix_target, "w", encoding="utf-8") as f:
                f.write(fixed_content)

            # Run language-specific validation
            lang = language.lower()
            if lang in ("java", "kotlin"):
                result = self._validate_java(repo_dir, fix_target, result)
            elif lang == "python":
                result = self._validate_python(repo_dir, fix_target, result)
            elif lang in ("javascript", "typescript"):
                result = self._validate_js(repo_dir, fix_target, lang, result)
            else:
                # For unsupported languages, just check file is valid UTF-8
                result.syntax_valid = True
                result.error_output = f"No validator for language: {language}"

        except Exception as exc:
            result.error_output = f"Sandbox validation error: {str(exc)}"
            logger.warning("Sandbox validation failed: %s", exc)
        finally:
            if tmp_dir and os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)

        return result

    def _run_cmd(self, cmd: list[str], cwd: str) -> tuple[int, str]:
        """Run a command with timeout and capture output."""
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
            return proc.returncode, output[-2000:]  # Truncate output
        except subprocess.TimeoutExpired:
            return -1, "Command timed out"
        except FileNotFoundError:
            return -1, f"Command not found: {cmd[0]}"
        except Exception as exc:
            return -1, str(exc)

    def _validate_java(self, repo_dir: str, file_path: str, result: ValidationResult) -> ValidationResult:
        # Try javac first
        rc, out = self._run_cmd(["javac", file_path], repo_dir)
        result.syntax_valid = rc == 0
        if not result.syntax_valid:
            result.error_output = out
            return result

        # Try maven compile
        if os.path.exists(os.path.join(repo_dir, "pom.xml")):
            rc, out = self._run_cmd(["mvn", "compile", "-q", "-B"], repo_dir)
            result.compile_valid = rc == 0
            if not result.compile_valid:
                result.error_output = out
                return result

            # Try maven test
            rc, out = self._run_cmd(["mvn", "test", "-q", "-B"], repo_dir)
            result.tests_pass = rc == 0
            if not result.tests_pass:
                result.error_output = out
        else:
            result.compile_valid = result.syntax_valid

        return result

    def _validate_python(self, repo_dir: str, file_path: str, result: ValidationResult) -> ValidationResult:
        # Syntax check
        rc, out = self._run_cmd(["python", "-m", "py_compile", file_path], repo_dir)
        result.syntax_valid = rc == 0
        if not result.syntax_valid:
            result.error_output = out
            return result

        result.compile_valid = True

        # Try pytest
        if os.path.exists(os.path.join(repo_dir, "pytest.ini")) or \
           os.path.exists(os.path.join(repo_dir, "setup.py")) or \
           os.path.exists(os.path.join(repo_dir, "pyproject.toml")):
            rc, out = self._run_cmd(["python", "-m", "pytest", "-q", "--tb=short", "-x"], repo_dir)
            result.tests_pass = rc == 0
            if not result.tests_pass:
                result.error_output = out

        return result

    def _validate_js(self, repo_dir: str, file_path: str, lang: str, result: ValidationResult) -> ValidationResult:
        if lang == "typescript":
            # Check with tsc
            rc, out = self._run_cmd(["npx", "tsc", "--noEmit"], repo_dir)
            result.syntax_valid = rc == 0
            if not result.syntax_valid:
                result.error_output = out
                return result
        else:
            # Check with node
            rc, out = self._run_cmd(["node", "--check", file_path], repo_dir)
            result.syntax_valid = rc == 0
            if not result.syntax_valid:
                result.error_output = out
                return result

        result.compile_valid = result.syntax_valid

        # Try npm test
        if os.path.exists(os.path.join(repo_dir, "package.json")):
            rc, out = self._run_cmd(["npm", "test", "--if-present"], repo_dir)
            result.tests_pass = rc == 0
            if not result.tests_pass:
                result.error_output = out

        return result
