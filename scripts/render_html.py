"""Render a table HTML fragment to a cropped PNG."""

from __future__ import annotations

import argparse
import io
from pathlib import Path

from PIL import Image, ImageChops


_DOC_BOILERPLATE = """<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
@page { size: 30cm 42cm; margin: 1cm; }
body { margin: 0; padding: 0; font-family: "Noto Sans", "Noto Sans Devanagari", "Noto Sans CJK SC", sans-serif; font-size: 13px; color: #111; background: #fff; }
table { border-collapse: collapse !important; border-spacing: 0 !important; }
table, th, td { border: 1px solid #7f8a9a !important; }
th, td { padding: 4px 6px; vertical-align: top; }
td { font-weight: 400; }
th { font-weight: 700; text-align: center; }
</style></head><body>__HTML__</body></html>"""


def render_html_to_png(
    html: str,
    *,
    scale: float = 2.0,
    auto_crop: bool = True,
    max_pixels: int | None = 1_505_280,
) -> bytes:
    """Render an HTML fragment to PNG bytes."""
    import pypdfium2 as pdfium
    import weasyprint

    pdf = weasyprint.HTML(
        string=_DOC_BOILERPLATE.replace("__HTML__", html)
    ).write_pdf()
    document = pdfium.PdfDocument(io.BytesIO(pdf))
    page = None
    bitmap = None
    try:
        page = document[0]
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil().convert("RGB")
    finally:
        if bitmap is not None:
            bitmap.close()
        if page is not None:
            page.close()
        document.close()
    if auto_crop:
        image = _auto_crop_white(image)
    if max_pixels and image.width * image.height > max_pixels:
        factor = (max_pixels / (image.width * image.height)) ** 0.5
        image = image.resize(
            (max(1, int(image.width * factor)), max(1, int(image.height * factor))),
            Image.Resampling.LANCZOS,
        )
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _auto_crop_white(image: Image.Image, pad: int = 6) -> Image.Image:
    background = Image.new(image.mode, image.size, (255, 255, 255))
    bounds = ImageChops.difference(image, background).getbbox()
    if not bounds:
        return image
    left, top, right, bottom = bounds
    return image.crop((
        max(0, left - pad),
        max(0, top - pad),
        min(image.width, right + pad),
        min(image.height, bottom + pad),
    ))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_html", type=Path)
    parser.add_argument("output_png", type=Path)
    args = parser.parse_args()
    args.output_png.write_bytes(
        render_html_to_png(args.input_html.read_text(encoding="utf-8"))
    )


if __name__ == "__main__":
    main()
