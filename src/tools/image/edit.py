"""
Image Editing
Part of SOVEREIGN PYTHON LLM ENGINE

Edit images using PIL/Pillow.
"""

from typing import Any
from pathlib import Path
from dataclasses import dataclass
from io import BytesIO


@dataclass
class EditedImage:
    """Edited image result"""
    image_bytes: bytes
    format: str
    size: tuple[int, int]
    operations: list[str]


class ImageEditor:
    """
    Image editing operations using Pillow.

    Supports:
    - Resize, crop, rotate
    - Format conversion
    - Filters and adjustments
    - Watermarking
    """

    def __init__(self):
        try:
            from PIL import Image
        except ImportError:
            raise ImportError("Pillow is required. Install: pip install Pillow")

    async def resize(
        self,
        image_path: Path,
        width: int,
        height: int,
        maintain_aspect: bool = True
    ) -> EditedImage:
        """
        Resize image.

        Args:
            image_path: Input image
            width: Target width
            height: Target height
            maintain_aspect: Maintain aspect ratio

        Returns:
            EditedImage
        """
        from PIL import Image
        import asyncio

        def _sync_resize():
            img = Image.open(image_path)

            if maintain_aspect:
                img.thumbnail((width, height), Image.Resampling.LANCZOS)
            else:
                img = img.resize((width, height), Image.Resampling.LANCZOS)

            # Save to bytes
            buffer = BytesIO()
            img.save(buffer, format=img.format or "PNG")
            buffer.seek(0)

            return EditedImage(
                image_bytes=buffer.read(),
                format=img.format or "PNG",
                size=img.size,
                operations=["resize"]
            )

        return await asyncio.to_thread(_sync_resize)

    async def crop(
        self,
        image_path: Path,
        left: int,
        top: int,
        right: int,
        bottom: int
    ) -> EditedImage:
        """
        Crop image.

        Args:
            image_path: Input image
            left, top, right, bottom: Crop box

        Returns:
            EditedImage
        """
        from PIL import Image
        import asyncio

        def _sync_crop():
            img = Image.open(image_path)
            img = img.crop((left, top, right, bottom))

            buffer = BytesIO()
            img.save(buffer, format=img.format or "PNG")
            buffer.seek(0)

            return EditedImage(
                image_bytes=buffer.read(),
                format=img.format or "PNG",
                size=img.size,
                operations=["crop"]
            )

        return await asyncio.to_thread(_sync_crop)

    async def rotate(
        self,
        image_path: Path,
        angle: float,
        expand: bool = True
    ) -> EditedImage:
        """
        Rotate image.

        Args:
            image_path: Input image
            angle: Rotation angle in degrees
            expand: Expand image to fit rotated content

        Returns:
            EditedImage
        """
        from PIL import Image
        import asyncio

        def _sync_rotate():
            img = Image.open(image_path)
            img = img.rotate(angle, expand=expand)

            buffer = BytesIO()
            img.save(buffer, format=img.format or "PNG")
            buffer.seek(0)

            return EditedImage(
                image_bytes=buffer.read(),
                format=img.format or "PNG",
                size=img.size,
                operations=["rotate"]
            )

        return await asyncio.to_thread(_sync_rotate)

    async def convert_format(
        self,
        image_path: Path,
        target_format: str
    ) -> EditedImage:
        """
        Convert image format.

        Args:
            image_path: Input image
            target_format: Target format ("PNG", "JPEG", "WEBP", etc.)

        Returns:
            EditedImage
        """
        from PIL import Image
        import asyncio

        def _sync_convert():
            img = Image.open(image_path)

            # Convert RGBA to RGB if saving as JPEG
            if target_format.upper() == "JPEG" and img.mode == "RGBA":
                img = img.convert("RGB")

            buffer = BytesIO()
            img.save(buffer, format=target_format)
            buffer.seek(0)

            return EditedImage(
                image_bytes=buffer.read(),
                format=target_format,
                size=img.size,
                operations=["convert"]
            )

        return await asyncio.to_thread(_sync_convert)

    async def apply_filter(
        self,
        image_path: Path,
        filter_name: str
    ) -> EditedImage:
        """
        Apply filter to image.

        Args:
            image_path: Input image
            filter_name: Filter name ("blur", "sharpen", "contour", etc.)

        Returns:
            EditedImage
        """
        from PIL import Image, ImageFilter
        import asyncio

        def _sync_filter():
            img = Image.open(image_path)

            # Map filter names
            filters = {
                "blur": ImageFilter.BLUR,
                "sharpen": ImageFilter.SHARPEN,
                "contour": ImageFilter.CONTOUR,
                "detail": ImageFilter.DETAIL,
                "edge_enhance": ImageFilter.EDGE_ENHANCE,
                "smooth": ImageFilter.SMOOTH,
            }

            filter_obj = filters.get(filter_name.lower())
            if not filter_obj:
                raise ValueError(f"Unknown filter: {filter_name}")

            img = img.filter(filter_obj)

            buffer = BytesIO()
            img.save(buffer, format=img.format or "PNG")
            buffer.seek(0)

            return EditedImage(
                image_bytes=buffer.read(),
                format=img.format or "PNG",
                size=img.size,
                operations=[f"filter:{filter_name}"]
            )

        return await asyncio.to_thread(_sync_filter)


# Tool registration helpers
async def resize_image_tool(
    image_path: str,
    width: int,
    height: int,
    output_path: str | None = None
) -> dict:
    """Resize image tool"""
    editor = ImageEditor()
    result = await editor.resize(Path(image_path), width, height)

    if output_path:
        Path(output_path).write_bytes(result.image_bytes)

    return {
        "size": result.size,
        "format": result.format,
        "operations": result.operations
    }


async def convert_image_tool(
    image_path: str,
    target_format: str,
    output_path: str | None = None
) -> dict:
    """Convert image format tool"""
    editor = ImageEditor()
    result = await editor.convert_format(Path(image_path), target_format)

    if output_path:
        Path(output_path).write_bytes(result.image_bytes)

    return {
        "format": result.format,
        "size": result.size
    }
