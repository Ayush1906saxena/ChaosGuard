"""Tests for SandboxValidator (agents/generators/sandbox_validator.py).

Covers syntax validation for Python, Java, JavaScript, and unknown languages,
missing clone paths, missing files, and command timeout handling.
"""

import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from generators.sandbox_validator import SandboxValidator, ValidationResult


@pytest.fixture
def validator():
    return SandboxValidator()


@pytest.fixture
def temp_repo():
    """Create a temporary directory with a sample Python file."""
    tmp = tempfile.mkdtemp(prefix="cg_test_repo_")
    os.makedirs(os.path.join(tmp, "src"), exist_ok=True)
    with open(os.path.join(tmp, "src", "app.py"), "w") as f:
        f.write("print('hello')\n")
    with open(os.path.join(tmp, "src", "Main.java"), "w") as f:
        f.write("public class Main { public static void main(String[] args) {} }\n")
    with open(os.path.join(tmp, "src", "index.js"), "w") as f:
        f.write("console.log('hello');\n")
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


# ── Python validation ────────────────────────────────────────────────


class TestPythonValidation:
    @patch.object(SandboxValidator, "_run_cmd")
    def test_validate_python_syntax_valid(self, mock_run, validator, temp_repo):
        """Valid Python syntax should set syntax_valid=True."""
        mock_run.return_value = (0, "")
        result = validator.validate(
            temp_repo, "src/app.py", "x = 1 + 2\n", "python"
        )
        assert result.syntax_valid is True

    @patch.object(SandboxValidator, "_run_cmd")
    def test_validate_python_syntax_invalid(self, mock_run, validator, temp_repo):
        """Invalid Python syntax should set syntax_valid=False with error output."""
        mock_run.return_value = (1, "SyntaxError: invalid syntax")
        result = validator.validate(
            temp_repo, "src/app.py", "def foo(:\n", "python"
        )
        assert result.syntax_valid is False
        assert "SyntaxError" in result.error_output


# ── Java validation ──────────────────────────────────────────────────


class TestJavaValidation:
    @patch.object(SandboxValidator, "_run_cmd")
    def test_validate_java_syntax_valid(self, mock_run, validator, temp_repo):
        """Valid Java source should set syntax_valid=True."""
        mock_run.return_value = (0, "")
        result = validator.validate(
            temp_repo,
            "src/Main.java",
            "public class Main { }",
            "java",
        )
        assert result.syntax_valid is True


# ── JavaScript validation ────────────────────────────────────────────


class TestJsValidation:
    @patch.object(SandboxValidator, "_run_cmd")
    def test_validate_js_syntax_valid(self, mock_run, validator, temp_repo):
        """Valid JavaScript should set syntax_valid=True."""
        mock_run.return_value = (0, "")
        result = validator.validate(
            temp_repo,
            "src/index.js",
            "const x = 42;\n",
            "javascript",
        )
        assert result.syntax_valid is True


# ── Unknown language ─────────────────────────────────────────────────


class TestUnknownLanguage:
    def test_validate_unknown_language_returns_syntax_valid(self, validator, temp_repo):
        """For an unsupported language, syntax_valid should default to True."""
        # We need a file to exist at the target path
        os.makedirs(os.path.join(temp_repo, "src"), exist_ok=True)
        target = os.path.join(temp_repo, "src", "main.rs")
        with open(target, "w") as f:
            f.write("fn main() {}")

        result = validator.validate(
            temp_repo, "src/main.rs", "fn main() {}", "rust"
        )
        assert result.syntax_valid is True
        assert "No validator" in result.error_output


# ── Missing clone path ───────────────────────────────────────────────


class TestMissingClonePath:
    def test_validate_missing_clone_path(self, validator):
        """When clone_path does not exist, should return an error result."""
        result = validator.validate(
            "/nonexistent/path", "src/app.py", "x = 1\n", "python"
        )
        assert result.syntax_valid is False
        assert "Clone path not available" in result.error_output


# ── Missing file ─────────────────────────────────────────────────────


class TestMissingFile:
    def test_validate_missing_file(self, validator, temp_repo):
        """When the target file is missing from the clone, should return an error."""
        result = validator.validate(
            temp_repo, "does/not/exist.py", "x = 1\n", "python"
        )
        assert result.syntax_valid is False
        assert "File not found" in result.error_output


# ── Command timeout ──────────────────────────────────────────────────


class TestCommandTimeout:
    @patch.object(SandboxValidator, "_run_cmd")
    def test_command_timeout_handling(self, mock_run, validator, temp_repo):
        """When the validation command times out, syntax_valid should be False."""
        mock_run.return_value = (-1, "Command timed out")
        result = validator.validate(
            temp_repo, "src/app.py", "x = 1\n", "python"
        )
        assert result.syntax_valid is False
        assert "timed out" in result.error_output
