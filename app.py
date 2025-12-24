from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from typing import List
import tempfile, os

from ocr_engine.vision_client import ocr_document_text
from ocr_engine.pdf_render import render_pdf_pages_to_jpeg_bytes
from ocr_engine.lease_parser import extract_lease_fields

from ocr_engine.validators import find_required_fields, template_keyword_score
from ocr_engine.gms_llm import analyze_contract_text

from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/extract")
async def extract(files: List[UploadFile] = File(...), llm: int = Query(0)):
    if not files:
        raise HTTPException(status_code=400, detail="파일이 필요합니다.")

    pdfs = [f for f in files if (f.filename or "").lower().endswith(".pdf")]
    imgs = [f for f in files if not (f.filename or "").lower().endswith(".pdf")]

    full_text = ""
    meta = {}

    if pdfs:
        if len(pdfs) != 1 or imgs:
            raise HTTPException(status_code=400, detail="PDF는 1개만, 이미지와 동시 업로드 불가")
        pdf = pdfs[0]
        content = await pdf.read()

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        try:
            tmp.write(content); tmp.close()
            page_bytes_list = render_pdf_pages_to_jpeg_bytes(tmp.name, zoom=2.0)
            for page_bytes in page_bytes_list:
                full_text += "\n" + ocr_document_text(page_bytes)
            meta = {"pages": len(page_bytes_list)}
        finally:
            try: os.remove(tmp.name)
            except: pass

    else:
        if len(imgs) > 2:
            raise HTTPException(status_code=400, detail="이미지는 최대 2장까지 업로드 가능")
        for img in imgs:
            b = await img.read()
            full_text += "\n" + ocr_document_text(b)
        meta = {"images": len(imgs)}

    extracted = extract_lease_fields(full_text)

    # --- analysis (flags) ---
    req = find_required_fields(full_text)
    tpl = template_keyword_score(full_text)

    flags = []
    if req["missing_fields"] or req["present_but_blank"]:
        flags.append("MISSING_REQUIRED_FIELD")
    # 템플릿 점수 기준은 데이터 보면서 조정(일단 6 미만이면 이상)
    if tpl["score"] < 6:
        flags.append("UNUSUAL_TEMPLATE")

    analysis = {
        "flags": flags,
        "missing_fields": req["missing_fields"],
        "present_but_blank": req["present_but_blank"],
        "template": tpl,
    }

    if llm == 1:
        analysis["llm"] = await analyze_contract_text(full_text)

    return {"status": "ok", **meta, "extracted": extracted, "analysis": analysis}
