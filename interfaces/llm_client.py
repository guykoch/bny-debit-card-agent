"""
The one place that talks to the AI model.

A thin wrapper around OpenAI's Chat Completions endpoint, written with the
standard library so the repository still needs nothing installed. It sends
messages (and, optionally, tool schemas or a JSON answer format) and returns
the model's reply. It decides nothing.

BNY note: BNY runs GPT-5.4 on-prem. Pointing this at their instance should be
a change of OPENAI_BASE_URL and the credential in config/settings.py, if their
gateway speaks the same API; otherwise only this file changes.
"""

import json
import urllib.error
import urllib.request

from config import settings


class ModelUnavailable(Exception):
    """The model could not be reached or refused the request."""


class OpenAIChatClient:
    def __init__(self, api_key: str = None, model: str = None, base_url: str = None,
                 reasoning_effort: str = None, timeout: int = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_MODEL
        self.base_url = (base_url or settings.OPENAI_BASE_URL).rstrip("/")
        self.reasoning_effort = reasoning_effort or settings.OPENAI_REASONING_EFFORT
        self.timeout = timeout or settings.OPENAI_TIMEOUT_SECONDS
        if not self.api_key:
            raise ModelUnavailable("OPENAI_API_KEY is not set.")

    def chat(self, messages: list[dict], tools: list[dict] = None,
             response_format: dict = None) -> dict:
        """
        One request to the model. Returns choices[0].message as a dict:
        {"role": "assistant", "content": str|None, "tool_calls": [...]|None}
        """
        body = {"model": self.model, "messages": messages}
        if self.reasoning_effort:
            body["reasoning_effort"] = self.reasoning_effort
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
            body["parallel_tool_calls"] = False        # one step at a time
        if response_format:
            body["response_format"] = response_format

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:400]
            raise ModelUnavailable(f"The model returned HTTP {e.code}: {detail}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ModelUnavailable(f"Could not reach the model: {e}") from e

        try:
            return data["choices"][0]["message"]
        except (KeyError, IndexError) as e:
            raise ModelUnavailable(f"Unexpected reply from the model: {str(data)[:300]}") from e


def tool_schema_for_model(tool: dict) -> dict:
    """tools/*.json  ->  the function format the Chat Completions API expects."""
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool["input_schema"],
        },
    }
