"""
Brave Search Provider
"""

import os
import httpx
from typing import Any


class BraveSearch:
    """Brave Search API"""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("BRAVE_API_KEY")
        self.base_url = "https://api.search.brave.com/res/v1"

    async def search(
        self,
        query: str,
        max_results: int = 5,
        **kwargs
    ) -> list[dict[str, Any]]:
        """Search via Brave API"""

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/web/search",
                params={"q": query, "count": max_results},
                headers={"X-Subscription-Token": self.api_key}
            )

            data = response.json()

            return [
                {
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": result.get("description", ""),
                    "score": 1.0
                }
                for result in data.get("web", {}).get("results", [])
            ]
