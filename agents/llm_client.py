import asyncio
import json
import logging
import re
import time
from typing import Any, Optional

import httpx

from config import config

logger = logging.getLogger(__name__)


class OllamaClient:
    """Async wrapper around the Ollama REST API with retry and JSON parsing."""

    def __init__(
        self,
        base_url: str = config.OLLAMA_BASE_URL,
        timeout: int = config.OLLAMA_TIMEOUT_SECONDS,
        max_retries: int = config.OLLAMA_MAX_RETRIES,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None
        self._metrics: Optional[Any] = None  # ScanMetrics instance, set externally

    def set_metrics(self, metrics: Any) -> None:
        """Attach a ScanMetrics instance for recording LLM call durations."""
        self._metrics = metrics

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout, connect=30.0),
            )
        return self._client

    async def generate(
        self,
        prompt: str,
        system: str = "",
        model: str = config.CODE_MODEL,
        temperature: float = 0.1,
        expect_json: bool = False,
    ) -> dict[str, Any]:
        """Send a prompt to Ollama and return the parsed response.

        Args:
            prompt: The user prompt text.
            system: Optional system prompt.
            model: Ollama model name.
            temperature: Sampling temperature.
            expect_json: If True, attempt to parse response as JSON.

        Returns:
            A dict with 'response' (str) and optionally 'parsed' (dict) keys.
        """
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": 4096,
                "num_predict": 4096,
            },
        }
        if system:
            payload["system"] = system

        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                client = await self._get_client()
                t0 = time.monotonic()
                resp = await client.post("/api/generate", json=payload)
                resp.raise_for_status()
                duration_s = time.monotonic() - t0
                data = resp.json()

                # Record metrics if available
                if self._metrics is not None:
                    try:
                        self._metrics.record_llm_call(model, duration_s)
                    except Exception:
                        pass  # Don't let metrics recording break the LLM flow

                result: dict[str, Any] = {"response": data.get("response", "")}
                if expect_json:
                    result["parsed"] = self._parse_json_response(result["response"])
                return result

            except (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    logger.warning(
                        "Ollama request failed (attempt %d/%d): %s. Retrying in %ds...",
                        attempt,
                        self.max_retries,
                        str(exc),
                        wait,
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(
                        "Ollama request failed after %d attempts: %s",
                        self.max_retries,
                        str(exc),
                    )

        raise RuntimeError(f"Ollama request failed after {self.max_retries} retries") from last_error

    @staticmethod
    def _parse_json_response(text: str) -> dict[str, Any]:
        """Extract JSON from LLM response, stripping markdown fences."""
        # Strip markdown code fences
        cleaned = re.sub(r"```(?:json)?\s*", "", text)
        cleaned = re.sub(r"```\s*$", "", cleaned, flags=re.MULTILINE)
        cleaned = cleaned.strip()

        # Try direct parse first
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Try to find a JSON object within the text
        brace_match = re.search(r"\{[\s\S]*\}", cleaned)
        if brace_match:
            try:
                return json.loads(brace_match.group())
            except json.JSONDecodeError:
                pass

        # Try to find a JSON array
        bracket_match = re.search(r"\[[\s\S]*\]", cleaned)
        if bracket_match:
            try:
                parsed = json.loads(bracket_match.group())
                return {"findings": parsed}
            except json.JSONDecodeError:
                pass

        # Fallback
        logger.warning("Could not parse JSON from LLM response, returning empty findings")
        return {"findings": []}

    async def is_healthy(self) -> bool:
        """Check whether Ollama is reachable."""
        try:
            client = await self._get_client()
            resp = await client.get("/api/tags")
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Shut down the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# Singleton instance
ollama_client = OllamaClient()
