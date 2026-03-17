import difflib
import logging
import os
from typing import Any

from config import config

logger = logging.getLogger(__name__)


class FixGenerator:
    def __init__(self):
        prompt_dir = os.path.join(os.path.dirname(__file__), "..", "prompts")
        fix_prompt_path = os.path.join(prompt_dir, "fix_generator_system.txt")
        validator_prompt_path = os.path.join(prompt_dir, "fix_validator_system.txt")
        with open(fix_prompt_path) as f:
            self.fix_system_prompt = f.read()
        with open(validator_prompt_path) as f:
            self.validator_system_prompt = f.read()
        self.model = config.CODE_MODEL
        self._sandbox = None

    def _get_sandbox(self):
        if self._sandbox is None:
            from generators.sandbox_validator import SandboxValidator
            self._sandbox = SandboxValidator()
        return self._sandbox

    async def generate_fixes(self, findings: list[dict], tier: str, clone_path: str = "") -> list[dict]:
        """Generate fixes for all findings based on the tier."""
        # Only generate fixes for high/critical severity to keep scan time reasonable with local LLM
        fixable_severities = {"high", "critical"}
        fixed_findings = []
        for finding in findings:
            try:
                # Skip fix generation for low-severity findings based on tier
                finding_severity = finding.get("severity", "").lower()
                if finding_severity not in fixable_severities:
                    fixed_findings.append(finding)
                    continue

                if tier == "RECON":
                    fix = await self.recon_fix(finding)
                else:
                    fix = await self.hunter_fix(finding)

                if fix:
                    # LLM validation (skip for RECON template fixes to avoid slow LLM calls)
                    if tier != "RECON":
                        validation = await self.validate_fix(finding, fix)
                        fix["validation"] = validation
                    else:
                        fix["validation"] = {
                            "addresses_vulnerability": True,
                            "introduces_issues": False,
                            "completeness": "partial",
                            "confidence": 70,
                            "notes": "Template-based fix (no LLM validation).",
                        }

                    # Sandbox validation (Task 4b)
                    if clone_path and fix.get("fixed_code"):
                        fp = finding.get("file_path", "")
                        if isinstance(fp, list):
                            fp = fp[0] if fp else ""
                        fp = str(fp)
                        sandbox_result = self._sandbox_validate(
                            clone_path,
                            fp,
                            fix["fixed_code"],
                            finding.get("language", "unknown"),
                        )
                        fix["syntax_valid"] = sandbox_result.get("syntax_valid", None)
                        fix["compile_valid"] = sandbox_result.get("compile_valid", None)
                        fix["tests_pass"] = sandbox_result.get("tests_pass", None)
                        fix["sandbox_output"] = sandbox_result.get("error_output", "")

                        # If syntax check fails, retry with error context (1 retry)
                        if not fix.get("syntax_valid") and tier != "RECON":
                            retry_fix = await self._retry_with_error(finding, fix, sandbox_result)
                            if retry_fix:
                                fix = retry_fix

                    finding["fix"] = fix
            except Exception as exc:
                logger.warning("Failed to generate fix for %s: %s", finding.get("id", "unknown"), exc)

            fixed_findings.append(finding)

        return fixed_findings

    def _sandbox_validate(self, clone_path: str, file_path: str, fixed_code: str, language: str) -> dict:
        """Run sandbox validation and return results as dict."""
        try:
            sandbox = self._get_sandbox()
            result = sandbox.validate(clone_path, file_path, fixed_code, language)
            return {
                "syntax_valid": result.syntax_valid,
                "compile_valid": result.compile_valid,
                "tests_pass": result.tests_pass,
                "error_output": result.error_output,
            }
        except Exception as exc:
            logger.warning("Sandbox validation failed: %s", exc)
            return {"error_output": str(exc)}

    async def _retry_with_error(self, finding: dict, original_fix: dict, sandbox_result: dict) -> dict | None:
        """Retry fix generation with compilation error context."""
        from llm_client import ollama_client

        error_output = sandbox_result.get("error_output", "")
        if not error_output:
            return None

        prompt = (
            f"The previous fix attempt failed compilation/syntax check.\n\n"
            f"Original finding: {finding.get('title', 'Untitled')}\n"
            f"Previous fix:\n{original_fix.get('fixed_code', '')}\n\n"
            f"Compilation error:\n{error_output[:1000]}\n\n"
            f"Please generate a corrected fix that addresses both the security vulnerability "
            f"and the compilation error. Return JSON with: description, original_code, fixed_code"
        )

        try:
            result = await ollama_client.generate(prompt, self.fix_system_prompt, model=self.model, expect_json=True)
            if isinstance(result, dict):
                parsed = result.get("parsed", {})
                fixed_code = parsed.get("fixed_code", "")
                if fixed_code:
                    fix = {
                        "type": "llm_generated_retry",
                        "description": parsed.get("description", "Retry fix after compilation failure."),
                        "original_code": parsed.get("original_code", original_fix.get("original_code", "")),
                        "fixed_code": fixed_code,
                        "diff": self.generate_diff(
                            parsed.get("original_code", ""), fixed_code, finding.get("file_path", "")
                        ),
                    }
                    return fix
        except Exception as exc:
            logger.warning("Fix retry failed: %s", exc)

        return None

    async def recon_fix(self, finding: dict) -> dict:
        """Generate template-based fixes for Recon findings."""
        category = finding.get("category", "")
        severity = finding.get("severity", "").lower()
        title = finding.get("title", "")
        file_path = finding.get("file_path", "")
        if isinstance(file_path, list):
            file_path = file_path[0] if file_path else ""
        evidence = finding.get("evidence", "")
        if isinstance(evidence, (dict, list)):
            evidence = str(evidence)

        fix = {
            "type": "template",
            "description": "",
            "original_code": "",
            "fixed_code": "",
            "diff": "",
        }

        if category == "secret":
            # Secret -> env var replacement
            secret_name = title.upper().replace(" ", "_").replace("-", "_")
            fix["description"] = (
                f"Move the hardcoded secret to an environment variable. "
                f"Remove the secret from source code and use os.getenv('{secret_name}') "
                f"or equivalent for your language."
            )
            fix["original_code"] = evidence
            fix["fixed_code"] = f'os.getenv("{secret_name}")'
            fix["diff"] = self.generate_diff(
                evidence, f'os.getenv("{secret_name}")', file_path
            )

        elif category == "configuration":
            if "root" in title.lower() or "USER" in title:
                fix["description"] = (
                    "Add a non-root USER instruction to the Dockerfile to run the "
                    "container with least privileges."
                )
                fix["original_code"] = evidence
                fix["fixed_code"] = "USER nonroot"
                fix["diff"] = self.generate_diff(evidence, "USER nonroot", file_path)
            elif "debug" in title.lower():
                fix["description"] = "Disable debug mode in production configuration."
                fix["original_code"] = evidence
                fix["fixed_code"] = evidence.replace("true", "false").replace("True", "False")
                fix["diff"] = self.generate_diff(
                    evidence, fix["fixed_code"], file_path
                )
            elif "latest" in title.lower():
                fix["description"] = "Pin the base image to a specific version tag."
                fix["original_code"] = evidence
                fix["fixed_code"] = evidence.replace(":latest", ":22.04")  # example
                fix["diff"] = self.generate_diff(
                    evidence, fix["fixed_code"], file_path
                )
            else:
                fix["description"] = finding.get("remediation", "Apply the recommended fix.")
                fix["original_code"] = evidence

        elif category == "dependency":
            # Vulnerable dependency -> upgrade version
            remediation = finding.get("remediation", "")
            fix["description"] = remediation or "Upgrade the dependency to a patched version."
            fix["original_code"] = evidence

            # Try to extract target version from remediation
            import re
            version_match = re.search(r"version\s+(\S+)", remediation)
            if version_match:
                target_version = version_match.group(1).rstrip(".")
                fix["fixed_code"] = f"Upgrade to version {target_version}"
            else:
                fix["fixed_code"] = "Upgrade to the latest patched version."

        else:
            fix["description"] = finding.get("remediation", "Review and apply the recommended fix.")
            fix["original_code"] = evidence

        return fix

    async def hunter_fix(self, finding: dict) -> dict:
        """Generate LLM-powered contextual fixes for Hunter/Siege findings."""
        from llm_client import ollama_client

        prompt = (
            f"Generate a code fix for the following security finding.\n\n"
            f"Title: {finding.get('title', 'Untitled')}\n"
            f"Severity: {finding.get('severity', 'UNKNOWN')}\n"
            f"Category: {finding.get('category', 'unknown')}\n"
            f"File: {finding.get('file_path', 'unknown')}\n"
            f"Line: {finding.get('line', 'N/A')}\n"
            f"Evidence: {finding.get('evidence', 'N/A')}\n"
            f"Description: {finding.get('description', 'N/A')}\n"
            f"Remediation guidance: {finding.get('remediation', 'N/A')}\n\n"
            f"Provide:\n"
            f"1. A description of what the fix does\n"
            f"2. The original vulnerable code snippet\n"
            f"3. The fixed code snippet\n\n"
            f"Return JSON with: description, original_code, fixed_code"
        )

        result = await ollama_client.generate(prompt, self.fix_system_prompt, model=self.model, expect_json=True)

        fix_data = {}
        if isinstance(result, dict):
            fix_data = result.get("parsed", {})

        original_code = fix_data.get("original_code", finding.get("evidence", ""))
        if isinstance(original_code, (dict, list)):
            original_code = str(original_code)
        fixed_code = fix_data.get("fixed_code", "")
        if isinstance(fixed_code, (dict, list)):
            fixed_code = str(fixed_code)
        file_path = finding.get("file_path", "unknown")
        if isinstance(file_path, list):
            file_path = file_path[0] if file_path else "unknown"

        fix = {
            "type": "llm_generated",
            "description": fix_data.get("description", "LLM-generated fix."),
            "original_code": original_code,
            "fixed_code": fixed_code,
            "diff": self.generate_diff(original_code, fixed_code, file_path) if fixed_code else "",
        }

        return fix

    async def validate_fix(self, finding: dict, fix: dict) -> dict:
        """Use LLM to self-validate a generated fix."""
        from llm_client import ollama_client

        prompt = (
            f"Validate the following security fix.\n\n"
            f"Original Finding: {finding.get('title', 'Untitled')} "
            f"({finding.get('severity', 'UNKNOWN')})\n"
            f"Category: {finding.get('category', 'unknown')}\n"
            f"Description: {finding.get('description', 'N/A')}\n\n"
            f"Proposed Fix:\n"
            f"Description: {fix.get('description', 'N/A')}\n"
            f"Original code: {fix.get('original_code', 'N/A')}\n"
            f"Fixed code: {fix.get('fixed_code', 'N/A')}\n\n"
            f"Evaluate:\n"
            f"1. Does this fix address the vulnerability?\n"
            f"2. Does it introduce any new issues?\n"
            f"3. Is the fix complete or partial?\n"
            f"4. Confidence score (0-100)\n\n"
            f"Return JSON with: addresses_vulnerability (bool), introduces_issues (bool), "
            f"completeness ('complete'|'partial'|'insufficient'), confidence (int), notes (str)"
        )

        result = await ollama_client.generate(prompt, self.validator_system_prompt, model=self.model, expect_json=True)

        validation = {
            "addresses_vulnerability": True,
            "introduces_issues": False,
            "completeness": "partial",
            "confidence": 50,
            "notes": "Validation could not be completed.",
        }

        if isinstance(result, dict):
            parsed = result.get("parsed", {})
            validation["addresses_vulnerability"] = parsed.get("addresses_vulnerability", True)
            validation["introduces_issues"] = parsed.get("introduces_issues", False)
            validation["completeness"] = parsed.get("completeness", "partial")
            validation["confidence"] = parsed.get("confidence", 50)
            validation["notes"] = parsed.get("notes", "")

        return validation

    def generate_diff(self, original: str, fixed: str, file_path: str = "file") -> str:
        """Create a unified diff from original to fixed code."""
        # Coerce to str in case LLM returned non-string types
        if isinstance(original, (dict, list)):
            original = str(original)
        if isinstance(fixed, (dict, list)):
            fixed = str(fixed)
        if isinstance(file_path, list):
            file_path = file_path[0] if file_path else "file"
        if not original or not fixed:
            return ""

        original_lines = original.splitlines(keepends=True)
        fixed_lines = fixed.splitlines(keepends=True)

        # Ensure lines end with newlines for proper diff formatting
        if original_lines and not original_lines[-1].endswith("\n"):
            original_lines[-1] += "\n"
        if fixed_lines and not fixed_lines[-1].endswith("\n"):
            fixed_lines[-1] += "\n"

        diff = difflib.unified_diff(
            original_lines,
            fixed_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )
        return "".join(diff)
