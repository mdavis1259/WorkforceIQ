"""OllamaClient: the ONLY class that talks to Ollama (SDS section 8.5).

Sends a non-streaming request with temperature 0 and JSON output to the local
Ollama server and returns the parsed JSON. Raises OllamaError if Ollama is
down, too slow (10 second timeout), or returns anything that is not JSON.
"""
import json

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2"
TIMEOUT_SECONDS = 10


class OllamaError(Exception):
    """Ollama is unavailable, too slow, or returned bad output."""


class OllamaClient:
    def __init__(self, url=OLLAMA_URL, model=MODEL,
                 timeout=TIMEOUT_SECONDS, http_post=None):
        self.url = url
        self.model = model
        self.timeout = timeout
        # http_post is injectable so tests never need a real Ollama server.
        self._post = http_post or requests.post

    def generate_json(self, prompt):
        payload = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0},
        }
        try:
            response = self._post(self.url, json=payload,
                                  timeout=self.timeout)
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as error:
            raise OllamaError(f"Ollama request failed: {error}") from error

        text = body.get("response") if isinstance(body, dict) else None
        if not isinstance(text, str):
            raise OllamaError("Ollama returned no response text.")
        try:
            result = json.loads(text)
        except ValueError as error:
            raise OllamaError("Ollama did not return valid JSON.") from error
        if not isinstance(result, dict):
            raise OllamaError("Ollama JSON was not an object.")
        return result

    def is_available(self):
        """Used by the health endpoint. Never raises."""
        try:
            base = self.url.rsplit("/api/", 1)[0]
            return self._get_ok(base + "/api/tags")
        except Exception:
            return False

    def _get_ok(self, url):
        return requests.get(url, timeout=2).ok
