from google.cloud import vision

def ocr_document_text(image_bytes: bytes) -> str:
    """
    Google Vision DOCUMENT_TEXT_DETECTION로 문서 OCR 수행.
    반환: 전체 텍스트(문서 단위)
    """
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_bytes)

    response = client.document_text_detection(image=image)

    if response.error and response.error.message:
        raise RuntimeError(f"Vision OCR error: {response.error.message}")

    # document_text_detection은 full_text_annotation에 문서 전체가 들어오는 편
    if response.full_text_annotation and response.full_text_annotation.text:
        return response.full_text_annotation.text

    # fallback (거의 안 타지만 안전용)
    if response.text_annotations:
        return response.text_annotations[0].description

    return ""
