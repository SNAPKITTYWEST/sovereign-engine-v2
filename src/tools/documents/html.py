"""
HTML Parser
Part of SOVEREIGN PYTHON LLM ENGINE

Parse HTML documents and extract clean text.
"""

from typing import Any
from pathlib import Path
from dataclasses import dataclass
import re


@dataclass
class HTMLDocument:
    """Parsed HTML document"""
    text: str
    title: str | None
    links: list[dict[str, str]]
    images: list[dict[str, str]]
    metadata: dict[str, Any]


class HTMLParser:
    """
    HTML document parser using BeautifulSoup.

    Extracts:
    - Clean text (no tags)
    - Title
    - Links
    - Images
    - Meta tags
    """

    def __init__(self, remove_scripts: bool = True, remove_styles: bool = True):
        """
        Initialize HTML parser.

        Args:
            remove_scripts: Remove <script> tags
            remove_styles: Remove <style> tags
        """
        self.remove_scripts = remove_scripts
        self.remove_styles = remove_styles

    async def parse(self, file_path: Path) -> HTMLDocument:
        """
        Parse HTML file.

        Args:
            file_path: Path to HTML file

        Returns:
            HTMLDocument
        """
        html = file_path.read_text(encoding="utf-8")
        return self.parse_html(html)

    def parse_html(self, html: str) -> HTMLDocument:
        """
        Parse HTML string.

        Args:
            html: HTML content

        Returns:
            HTMLDocument
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError("beautifulsoup4 is required. Install: pip install beautifulsoup4")

        soup = BeautifulSoup(html, "html.parser")

        # Remove scripts and styles
        if self.remove_scripts:
            for script in soup(["script"]):
                script.decompose()

        if self.remove_styles:
            for style in soup(["style"]):
                style.decompose()

        # Extract title
        title = None
        if soup.title:
            title = soup.title.string

        # Extract clean text
        text = soup.get_text(separator="\n", strip=True)

        # Extract links
        links = []
        for link in soup.find_all("a", href=True):
            links.append({
                "text": link.get_text(strip=True),
                "href": link["href"]
            })

        # Extract images
        images = []
        for img in soup.find_all("img"):
            images.append({
                "src": img.get("src", ""),
                "alt": img.get("alt", "")
            })

        # Extract metadata
        metadata = {}
        for meta in soup.find_all("meta"):
            name = meta.get("name") or meta.get("property")
            content = meta.get("content")
            if name and content:
                metadata[name] = content

        return HTMLDocument(
            text=text,
            title=title,
            links=links,
            images=images,
            metadata=metadata
        )


class ReadabilityParser:
    """
    Extract main content from HTML using readability algorithm.

    Removes boilerplate (headers, footers, navigation, ads).
    """

    def __init__(self):
        pass

    async def parse(self, html: str, url: str | None = None) -> dict:
        """
        Parse HTML and extract main content.

        Args:
            html: HTML content
            url: Optional URL for resolving relative links

        Returns:
            Dictionary with title, content, author, etc.
        """
        try:
            from readability import Document
        except ImportError:
            raise ImportError("readability-lxml is required. Install: pip install readability-lxml")

        doc = Document(html, url=url)

        return {
            "title": doc.title(),
            "content": doc.summary(html_partial=False),
            "short_title": doc.short_title(),
        }


# Tool registration helper
async def parse_html_tool(file_path: str) -> dict:
    """
    Tool wrapper for HTML parsing.

    Args:
        file_path: Path to HTML file

    Returns:
        Dictionary with parsed content
    """
    parser = HTMLParser()
    result = await parser.parse(Path(file_path))

    return {
        "text": result.text,
        "title": result.title,
        "links_count": len(result.links),
        "images_count": len(result.images),
        "metadata": result.metadata
    }


async def extract_readable_content_tool(html: str, url: str | None = None) -> dict:
    """
    Tool wrapper for readability extraction.

    Args:
        html: HTML content
        url: Optional URL

    Returns:
        Dictionary with main content
    """
    parser = ReadabilityParser()
    return await parser.parse(html, url)
