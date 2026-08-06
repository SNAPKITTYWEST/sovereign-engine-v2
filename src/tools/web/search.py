"""
Web Search and Fetching Tools
Part of SOVEREIGN PYTHON LLM ENGINE
"""

from typing import Any
import httpx
from bs4 import BeautifulSoup

from ..registry import tool, RiskClass, ApprovalPolicy


@tool(
    tool_id="web.search",
    version="1.0.0",
    title="Web Search",
    description="Search the web using Tavily or Brave Search API",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "max_results": {"type": "integer", "default": 5},
            "search_depth": {"type": "string", "enum": ["basic", "advanced"], "default": "basic"},
            "provider": {"type": "string", "enum": ["tavily", "brave"], "default": "tavily"}
        },
        "required": ["query"]
    },
    output_schema={
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                        "content": {"type": "string"},
                        "score": {"type": "number"}
                    }
                }
            },
            "query": {"type": "string"}
        }
    },
    risk_class=RiskClass.READ_ONLY_REMOTE,
    approval_policy=ApprovalPolicy.AUTOMATIC,
    tags=["web", "search", "rag"]
)
async def web_search(params: dict[str, Any]) -> dict[str, Any]:
    """
    Search the web.

    Args:
        params: {query, max_results, search_depth, provider}

    Returns:
        {results, query}
    """
    query = params['query']
    max_results = params.get('max_results', 5)
    search_depth = params.get('search_depth', 'basic')
    provider = params.get('provider', 'tavily')

    if provider == 'tavily':
        from .providers.tavily import TavilySearch
        provider_impl = TavilySearch()
    elif provider == 'brave':
        from .providers.brave import BraveSearch
        provider_impl = BraveSearch()
    else:
        raise ValueError(f"Unknown provider: {provider}")

    results = await provider_impl.search(
        query=query,
        max_results=max_results,
        search_depth=search_depth
    )

    return {
        'results': results,
        'query': query
    }


@tool(
    tool_id="web.fetch",
    version="1.0.0",
    title="Fetch Web Page",
    description="Fetch content from URL",
    input_schema={
        "type": "object",
        "properties": {
            "url": {"type": "string", "format": "uri"},
            "timeout": {"type": "integer", "default": 30}
        },
        "required": ["url"]
    },
    output_schema={
        "type": "object",
        "properties": {
            "content": {"type": "string"},
            "status_code": {"type": "integer"},
            "url": {"type": "string"}
        }
    },
    risk_class=RiskClass.READ_ONLY_REMOTE,
    approval_policy=ApprovalPolicy.AUTOMATIC,
    tags=["web", "fetch", "http"]
)
async def web_fetch(params: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch web page content.

    Args:
        params: {url, timeout}

    Returns:
        {content, status_code, url}
    """
    url = params['url']
    timeout = params.get('timeout', 30)

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)

        return {
            'content': response.text,
            'status_code': response.status_code,
            'url': str(response.url)
        }


@tool(
    tool_id="web.extract",
    version="1.0.0",
    title="Extract Clean Text from HTML",
    description="Extract clean text content from HTML",
    input_schema={
        "type": "object",
        "properties": {
            "html": {"type": "string"}
        },
        "required": ["html"]
    },
    output_schema={
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "title": {"type": "string"}
        }
    },
    risk_class=RiskClass.PURE_COMPUTATION,
    approval_policy=ApprovalPolicy.AUTOMATIC,
    tags=["web", "parsing", "extraction"]
)
async def web_extract(params: dict[str, Any]) -> dict[str, Any]:
    """
    Extract clean text from HTML.

    Args:
        params: {html}

    Returns:
        {text, title}
    """
    html = params['html']

    soup = BeautifulSoup(html, 'html.parser')

    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.decompose()

    # Get text
    text = soup.get_text()

    # Clean up whitespace
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = '\n'.join(chunk for chunk in chunks if chunk)

    # Get title
    title = soup.title.string if soup.title else ""

    return {
        'text': text,
        'title': title
    }
