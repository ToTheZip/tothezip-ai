import fitz  # PyMuPDF
import cv2
import numpy as np

def render_pdf_pages_to_jpeg_bytes(pdf_path: str, zoom: float = 2.0) -> list[bytes]:
    """
    PDF를 페이지별 JPEG bytes 리스트로 변환.
    """
    doc = fitz.open(pdf_path)
    outputs: list[bytes] = []

    mat = fitz.Matrix(zoom, zoom)
    for i in range(len(doc)):
        page = doc.load_page(i)
        pix = page.get_pixmap(matrix=mat)

        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        if pix.n >= 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        # (선택) 최소 전처리: 그레이스케일
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        ok, encoded = cv2.imencode(".jpg", gray)
        if not ok:
            raise RuntimeError("PDF page -> JPEG 인코딩 실패")
        outputs.append(encoded.tobytes())

    return outputs
