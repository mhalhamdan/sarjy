from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from app.config import Settings

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "remember",
        "description": (
            "Save a fact about the user to long-term memory, or replace an existing fact. "
            "Use when the user shares a preference, personal detail, or anything they'd "
            "expect you to know next time."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The fact as a standalone statement, under 500 characters.",
                },
                "replaces_id": {
                    "type": "integer",
                    "description": "Id of a remembered fact this one replaces, if any.",
                },
            },
            "required": ["content"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "forget",
        "description": "Delete a remembered fact when the user asks you to forget it.",
        "parameters": {
            "type": "object",
            "properties": {
                "memory_id": {"type": "integer", "description": "Id of the fact to delete."},
            },
            "required": ["memory_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "web_search",
        "description": (
            "Search the web for current or factual information: news, weather, sports, "
            "prices, opening hours, recent events. Returns a short answer to read aloud."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A specific search query, including any needed context "
                    "such as the user's city.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
]


def build_session_config(settings: Settings, instructions: str) -> dict[str, Any]:
    return {
        "type": "realtime",
        "model": settings.realtime_model,
        "instructions": instructions,
        "output_modalities": ["audio"],
        "reasoning": {"effort": settings.realtime_reasoning_effort},
        "audio": {
            "input": {
                "noise_reduction": {"type": "near_field"},
                "transcription": {"model": settings.transcription_model},
                # Semantic VAD at high eagerness replies as soon as the user sounds finished,
                # which favors latency; lower it if the assistant cuts people off.
                "turn_detection": {"type": "semantic_vad", "eagerness": "high"},
            },
            "output": {"voice": settings.realtime_voice},
        },
        "tools": TOOLS,
        "tool_choice": "auto",
    }


@dataclass(frozen=True)
class ClientSecret:
    value: str
    expires_at: int


class RealtimeService:
    """Mints short-lived client secrets so the browser can open the call directly with OpenAI.

    The standard API key never leaves the server; the browser only receives the ephemeral key.
    """

    def __init__(self, client: AsyncOpenAI, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def create_client_secret(self, instructions: str, safety_id: str) -> ClientSecret:
        secret = await self._client.realtime.client_secrets.create(
            expires_after={
                "anchor": "created_at",
                "seconds": self._settings.client_secret_ttl_seconds,
            },
            session=build_session_config(self._settings, instructions),
            extra_headers={"OpenAI-Safety-Identifier": safety_id},
        )
        return ClientSecret(value=secret.value, expires_at=secret.expires_at)
