import os

import fitz


def extract_pdf(
    pdf_path: str,
    image_output_dir: str,
    *,
    max_pages: int | None = 12,
    render_pages: bool = True,
    extract_embedded_images: bool = True,
) -> tuple[list[str], list[str]]:
    """
    Extract all page text and embedded images from a PDF.

    Returns (texts, image_paths).
    """
    os.makedirs(image_output_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    texts: list[str] = []
    image_paths: list[str] = []
    try:
        for page_idx, page in enumerate(doc):
            if max_pages is not None and page_idx >= max_pages:
                break
            texts.append(page.get_text())
            if render_pages:
                matrix = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                page_path = os.path.join(image_output_dir, f"pdf_page_{page_idx}.png")
                pix.save(page_path)
                image_paths.append(os.path.abspath(page_path))

            if not extract_embedded_images:
                continue

            for img_idx, img_info in enumerate(page.get_images(full=True)):
                xref = img_info[0]
                pix = fitz.Pixmap(doc, xref)
                try:
                    if pix.n > 4:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    p = os.path.join(image_output_dir, f"pdf_p{page_idx}_i{img_idx}.png")
                    pix.save(p)
                    image_paths.append(os.path.abspath(p))
                finally:
                    pix = None
    finally:
        doc.close()

    return texts, image_paths
