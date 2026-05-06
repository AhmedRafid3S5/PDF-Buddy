import base64
import fitz


def pdf_pages_to_images(pdf_path: str, start_page: int, end_page: int, dpi: int = 150) -> list[str]:
    if start_page < 1 or end_page < 1:
        raise ValueError("start_page and end_page must be >= 1")
    if end_page < start_page:
        raise ValueError("end_page must be >= start_page")

    images: list[str] = []
    with fitz.open(pdf_path) as doc:
        total_pages = doc.page_count
        if start_page > total_pages:
            return []

        last_page = min(end_page, total_pages)
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        for page_index in range(start_page - 1, last_page):
            page = doc.load_page(page_index)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("jpeg")
            images.append(base64.b64encode(img_bytes).decode("ascii"))

    return images