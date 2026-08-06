"""
PDF Parser
Part of SOVEREIGN PYTHON LLM ENGINE

Parse PDF documents to extract text, metadata, images.
"""

from typing import Any
from pathlib import Path
from dataclasses import dataclass
import io

from ...core.evidence import WORMLedger


@dataclass
class PDFDocument:
    """Parsed PDF document"""
    text: str
    pages: int
    metadata: dict[str, Any]
    images: list[bytes]
    tables: list[dict] | None = None


class PDFParser:
    """
    PDF document parser.

    Supports multiple backends:
    - pypdf2 (lightweight, pure Python)
    - pdfplumber (tables support)
    - pymupdf (fast, best quality)
    """

    def __init__(
        self,
        backend: str = "pypdf2",
        extract_images: bool = False,
        extract_tables: bool = False,
        worm_ledger: WORMLedger | None = None
    ):
        """
        Initialize PDF parser.

        Args:
            backend: Parser backend ("pypdf2", "pdfplumber", "pymupdf")
            extract_images: Whether to extract images
            extract_tables: Whether to extract tables
            worm_ledger: Optional WORM ledger
        """
        self.backend = backend
        self.extract_images = extract_images
        self.extract_tables = extract_tables
        self.worm_ledger = worm_ledger

        # Validate backend
        if backend not in ("pypdf2", "pdfplumber", "pymupdf"):
            raise ValueError(f"Unknown backend: {backend}")

    async def parse(self, file_path: Path) -> PDFDocument:
        """
        Parse PDF file.

        Args:
            file_path: Path to PDF file

        Returns:
            PDFDocument with extracted content
        """
        if self.backend == "pypdf2":
            return await self._parse_pypdf2(file_path)
        elif self.backend == "pdfplumber":
            return await self._parse_pdfplumber(file_path)
        elif self.backend == "pymupdf":
            return await self._parse_pymupdf(file_path)

    async def parse_bytes(self, pdf_bytes: bytes) -> PDFDocument:
        """
        Parse PDF from bytes.

        Args:
            pdf_bytes: PDF file bytes

        Returns:
            PDFDocument
        """
        if self.backend == "pypdf2":
            return await self._parse_pypdf2_bytes(pdf_bytes)
        elif self.backend == "pdfplumber":
            return await self._parse_pdfplumber_bytes(pdf_bytes)
        elif self.backend == "pymupdf":
            return await self._parse_pymupdf_bytes(pdf_bytes)

    async def _parse_pypdf2(self, file_path: Path) -> PDFDocument:
        """Parse using pypdf2"""
        try:
            import pypdf
        except ImportError:
            raise ImportError("pypdf is required. Install: pip install pypdf")

        import asyncio

        def _sync_parse():
            reader = pypdf.PdfReader(str(file_path))

            # Extract text
            text_parts = []
            for page in reader.pages:
                text_parts.append(page.extract_text())

            text = "\n\n".join(text_parts)

            # Extract metadata
            metadata = {}
            if reader.metadata:
                metadata = {
                    "title": reader.metadata.get("/Title", ""),
                    "author": reader.metadata.get("/Author", ""),
                    "subject": reader.metadata.get("/Subject", ""),
                    "creator": reader.metadata.get("/Creator", ""),
                    "producer": reader.metadata.get("/Producer", ""),
                }

            # Extract images (if requested)
            images = []
            if self.extract_images:
                for page in reader.pages:
                    if "/XObject" in page["/Resources"]:
                        x_object = page["/Resources"]["/XObject"].get_object()
                        for obj in x_object:
                            if x_object[obj]["/Subtype"] == "/Image":
                                try:
                                    img_data = x_object[obj].get_data()
                                    images.append(img_data)
                                except Exception:
                                    pass

            return PDFDocument(
                text=text,
                pages=len(reader.pages),
                metadata=metadata,
                images=images
            )

        # Run in thread pool
        return await asyncio.to_thread(_sync_parse)

    async def _parse_pypdf2_bytes(self, pdf_bytes: bytes) -> PDFDocument:
        """Parse bytes using pypdf2"""
        try:
            import pypdf
        except ImportError:
            raise ImportError("pypdf is required")

        import asyncio

        def _sync_parse():
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))

            text_parts = []
            for page in reader.pages:
                text_parts.append(page.extract_text())

            text = "\n\n".join(text_parts)

            metadata = {}
            if reader.metadata:
                metadata = {
                    "title": reader.metadata.get("/Title", ""),
                    "author": reader.metadata.get("/Author", ""),
                }

            return PDFDocument(
                text=text,
                pages=len(reader.pages),
                metadata=metadata,
                images=[]
            )

        return await asyncio.to_thread(_sync_parse)

    async def _parse_pdfplumber(self, file_path: Path) -> PDFDocument:
        """Parse using pdfplumber (best for tables)"""
        try:
            import pdfplumber
        except ImportError:
            raise ImportError("pdfplumber is required. Install: pip install pdfplumber")

        import asyncio

        def _sync_parse():
            with pdfplumber.open(file_path) as pdf:
                # Extract text
                text_parts = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)

                text = "\n\n".join(text_parts)

                # Extract tables (if requested)
                tables = []
                if self.extract_tables:
                    for page in pdf.pages:
                        page_tables = page.extract_tables()
                        for table in page_tables:
                            # Convert to dict format
                            if table and len(table) > 0:
                                headers = table[0]
                                rows = []
                                for row in table[1:]:
                                    row_dict = dict(zip(headers, row))
                                    rows.append(row_dict)
                                tables.append({"headers": headers, "rows": rows})

                # Metadata
                metadata = pdf.metadata or {}

                return PDFDocument(
                    text=text,
                    pages=len(pdf.pages),
                    metadata=metadata,
                    images=[],
                    tables=tables if tables else None
                )

        return await asyncio.to_thread(_sync_parse)

    async def _parse_pdfplumber_bytes(self, pdf_bytes: bytes) -> PDFDocument:
        """Parse bytes using pdfplumber"""
        try:
            import pdfplumber
        except ImportError:
            raise ImportError("pdfplumber is required")

        import asyncio

        def _sync_parse():
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                text_parts = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)

                return PDFDocument(
                    text="\n\n".join(text_parts),
                    pages=len(pdf.pages),
                    metadata=pdf.metadata or {},
                    images=[]
                )

        return await asyncio.to_thread(_sync_parse)

    async def _parse_pymupdf(self, file_path: Path) -> PDFDocument:
        """Parse using pymupdf (fastest, best quality)"""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("PyMuPDF is required. Install: pip install pymupdf")

        import asyncio

        def _sync_parse():
            doc = fitz.open(file_path)

            # Extract text
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())

            text = "\n\n".join(text_parts)

            # Extract images
            images = []
            if self.extract_images:
                for page in doc:
                    image_list = page.get_images()
                    for img in image_list:
                        xref = img[0]
                        try:
                            base_image = doc.extract_image(xref)
                            images.append(base_image["image"])
                        except Exception:
                            pass

            # Metadata
            metadata = doc.metadata

            doc.close()

            return PDFDocument(
                text=text,
                pages=len(doc),
                metadata=metadata,
                images=images
            )

        return await asyncio.to_thread(_sync_parse)

    async def _parse_pymupdf_bytes(self, pdf_bytes: bytes) -> PDFDocument:
        """Parse bytes using pymupdf"""
        try:
            import fitz
        except ImportError:
            raise ImportError("PyMuPDF is required")

        import asyncio

        def _sync_parse():
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())

            metadata = doc.metadata
            doc.close()

            return PDFDocument(
                text="\n\n".join(text_parts),
                pages=len(doc),
                metadata=metadata,
                images=[]
            )

        return await asyncio.to_thread(_sync_parse)


# Tool registration helper
async def parse_pdf_tool(
    file_path: str,
    extract_images: bool = False,
    extract_tables: bool = False
) -> dict:
    """
    Tool wrapper for PDF parsing.

    Args:
        file_path: Path to PDF file
        extract_images: Extract images
        extract_tables: Extract tables

    Returns:
        Dictionary with parsed content
    """
    parser = PDFParser(
        backend="pypdf2",
        extract_images=extract_images,
        extract_tables=extract_tables
    )

    result = await parser.parse(Path(file_path))

    return {
        "text": result.text,
        "pages": result.pages,
        "metadata": result.metadata,
        "images_count": len(result.images),
        "tables": result.tables
    }
