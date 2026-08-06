"""
Documents Namespace
Part of SOVEREIGN PYTHON LLM ENGINE

Document parsing tools for PDF, DOCX, Markdown, HTML, etc.
"""

from .pdf import PDFParser
from .docx import DOCXParser
from .markdown import MarkdownParser
from .html import HTMLParser

__all__ = [
    "PDFParser",
    "DOCXParser",
    "MarkdownParser",
    "HTMLParser",
]
