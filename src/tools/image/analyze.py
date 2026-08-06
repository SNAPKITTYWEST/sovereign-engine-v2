"""
Image Analysis
Part of SOVEREIGN PYTHON LLM ENGINE

Analyze images using vision models.
"""

from typing import Any
from pathlib import Path
from dataclasses import dataclass
import base64


@dataclass
class ImageAnalysis:
    """Image analysis result"""
    description: str
    labels: list[str]
    objects: list[dict[str, Any]]
    text: str | None
    metadata: dict[str, Any]


class ImageAnalyzer:
    """
    Image analysis using vision models.

    Supports:
    - OpenAI GPT-4 Vision
    - AWS Bedrock Claude with vision
    - Google Cloud Vision
    """

    def __init__(self, provider: str = "bedrock"):
        """
        Initialize image analyzer.

        Args:
            provider: Provider ("openai", "bedrock", "google")
        """
        self.provider = provider

    async def analyze(
        self,
        image_path: Path,
        prompt: str = "Describe this image in detail."
    ) -> ImageAnalysis:
        """
        Analyze image with vision model.

        Args:
            image_path: Path to image
            prompt: Analysis prompt

        Returns:
            ImageAnalysis
        """
        if self.provider == "bedrock":
            return await self._analyze_bedrock(image_path, prompt)
        elif self.provider == "openai":
            return await self._analyze_openai(image_path, prompt)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    async def _analyze_bedrock(
        self,
        image_path: Path,
        prompt: str
    ) -> ImageAnalysis:
        """Analyze using AWS Bedrock Claude"""
        import boto3
        import json

        client = boto3.client("bedrock-runtime", region_name="us-east-1")

        # Read image
        image_bytes = image_path.read_bytes()
        image_b64 = base64.b64encode(image_bytes).decode()

        # Determine format
        ext = image_path.suffix.lower().lstrip(".")
        media_type = f"image/{ext}" if ext in ("png", "jpeg", "jpg", "gif", "webp") else "image/png"

        # Build request
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        }

        # Invoke
        response = client.invoke_model(
            modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
            body=json.dumps(request_body)
        )

        # Parse
        response_body = json.loads(response["body"].read())
        description = response_body["content"][0]["text"]

        return ImageAnalysis(
            description=description,
            labels=[],
            objects=[],
            text=None,
            metadata={"model": "claude-3.5-sonnet"}
        )

    async def _analyze_openai(
        self,
        image_path: Path,
        prompt: str
    ) -> ImageAnalysis:
        """Analyze using OpenAI GPT-4 Vision"""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("openai is required")

        client = AsyncOpenAI()

        # Encode image
        image_bytes = image_path.read_bytes()
        image_b64 = base64.b64encode(image_bytes).decode()

        # Get extension
        ext = image_path.suffix.lower().lstrip(".")
        media_type = f"image/{ext}"

        # Create request
        response = await client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{image_b64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1024
        )

        description = response.choices[0].message.content

        return ImageAnalysis(
            description=description,
            labels=[],
            objects=[],
            text=None,
            metadata={"model": "gpt-4-vision"}
        )


# Tool registration helper
async def analyze_image_tool(
    image_path: str,
    prompt: str = "Describe this image in detail.",
    provider: str = "bedrock"
) -> dict:
    """Analyze image tool"""
    analyzer = ImageAnalyzer(provider=provider)
    result = await analyzer.analyze(Path(image_path), prompt)

    return {
        "description": result.description,
        "labels": result.labels,
        "metadata": result.metadata
    }
