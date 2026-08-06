"""
Markdown Parser
Part of SOVEREIGN PYTHON LLM ENGINE

Parse Markdown documents and convert to structured format.
"""

from typing import Any
from pathlib import Path
from dataclasses import dataclass
import re


@dataclass
class MarkdownDocument:
    """Parsed Markdown document"""
    text: str
    sections: list[dict[str, Any]]
    links: list[dict[str, str]]
    images: list[dict[str, str]]
    code_blocks: list[dict[str, str]]
    metadata: dict[str, Any]


class MarkdownParser:
    """
    Markdown document parser.

    Extracts:
    - Sections (by heading level)
    - Links
    - Images
    - Code blocks
    - Front matter (YAML)
    """

    def __init__(self):
        pass

    async def parse(self, file_path: Path) -> MarkdownDocument:
        """
        Parse Markdown file.

        Args:
            file_path: Path to Markdown file

        Returns:
            MarkdownDocument
        """
        text = file_path.read_text(encoding="utf-8")
        return self.parse_text(text)

    def parse_text(self, text: str) -> MarkdownDocument:
        """
        Parse Markdown text.

        Args:
            text: Markdown content

        Returns:
            MarkdownDocument
        """
        # Extract front matter (YAML)
        metadata, text = self._extract_front_matter(text)

        # Extract sections
        sections = self._extract_sections(text)

        # Extract links
        links = self._extract_links(text)

        # Extract images
        images = self._extract_images(text)

        # Extract code blocks
        code_blocks = self._extract_code_blocks(text)

        return MarkdownDocument(
            text=text,
            sections=sections,
            links=links,
            images=images,
            code_blocks=code_blocks,
            metadata=metadata
        )

    def _extract_front_matter(self, text: str) -> tuple[dict, str]:
        """Extract YAML front matter"""
        if not text.startswith("---"):
            return {}, text

        # Find end of front matter
        match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        if not match:
            return {}, text

        yaml_content = match.group(1)
        remaining_text = text[match.end():]

        # Parse YAML (simple key-value extraction)
        metadata = {}
        for line in yaml_content.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()

        return metadata, remaining_text

    def _extract_sections(self, text: str) -> list[dict[str, Any]]:
        """Extract sections by heading level"""
        sections = []
        lines = text.split("\n")

        current_section = None

        for line in lines:
            # Check if heading
            if line.startswith("#"):
                # Save previous section
                if current_section:
                    sections.append(current_section)

                # Start new section
                level = len(line) - len(line.lstrip("#"))
                title = line.lstrip("#").strip()

                current_section = {
                    "level": level,
                    "title": title,
                    "content": []
                }
            elif current_section is not None:
                current_section["content"].append(line)

        # Add last section
        if current_section:
            current_section["content"] = "\n".join(current_section["content"]).strip()
            sections.append(current_section)

        return sections

    def _extract_links(self, text: str) -> list[dict[str, str]]:
        """Extract Markdown links"""
        # Pattern: [text](url)
        pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
        matches = re.findall(pattern, text)

        links = []
        for text, url in matches:
            links.append({
                "text": text,
                "url": url
            })

        return links

    def _extract_images(self, text: str) -> list[dict[str, str]]:
        """Extract Markdown images"""
        # Pattern: ![alt](src)
        pattern = r'!\[([^\]]*)\]\(([^\)]+)\)'
        matches = re.findall(pattern, text)

        images = []
        for alt, src in matches:
            images.append({
                "alt": alt,
                "src": src
            })

        return images

    def _extract_code_blocks(self, text: str) -> list[dict[str, str]]:
        """Extract fenced code blocks"""
        # Pattern: ```language\ncode\n```
        pattern = r'```(\w*)\n(.*?)```'
        matches = re.findall(pattern, text, re.DOTALL)

        code_blocks = []
        for language, code in matches:
            code_blocks.append({
                "language": language or "text",
                "code": code.strip()
            })

        return code_blocks


# Tool registration helper
async def parse_markdown_tool(file_path: str) -> dict:
    """
    Tool wrapper for Markdown parsing.

    Args:
        file_path: Path to Markdown file

    Returns:
        Dictionary with parsed content
    """
    parser = MarkdownParser()
    result = await parser.parse(Path(file_path))

    return {
        "text": result.text,
        "sections_count": len(result.sections),
        "links_count": len(result.links),
        "images_count": len(result.images),
        "code_blocks_count": len(result.code_blocks),
        "metadata": result.metadata
    }
