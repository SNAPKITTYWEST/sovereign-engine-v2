"""
Bedrock inference backend — temporary stub until Ahmad's sovereign SDK ships.
Routes through AWS Bedrock using existing ~/.aws/credentials.
"""

from __future__ import annotations

import json
import boto3
from typing import AsyncIterator


class BedrockBackend:
    """
    AWS Bedrock inference backend.
    Temporary wire — Ahmad's sovereign SDK replaces this.
    """

    model_id: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

    def __init__(self, model_id: str | None = None, region: str = "us-east-1"):
        if model_id:
            self.model_id = model_id
        self._client = boto3.client("bedrock-runtime", region_name=region)

    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> str | AsyncIterator[str]:
        # Strip to role+content only — Anthropic rejects extra fields
        # System prompt goes to top-level, not in messages array
        system_parts = [m["content"] for m in messages if m.get("role") == "system"]
        clean_messages = [
            {"role": m["role"], "content": str(m["content"])}
            for m in messages if m.get("role") != "system"
        ]
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens or 1024,
            "temperature": temperature,
            "messages": clean_messages,
        }
        if system_parts:
            body["system"] = "\n".join(str(p) for p in system_parts)
        response = self._client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(body, default=str),
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]
