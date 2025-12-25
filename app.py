from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from typing import List
import tempfile, os

from ocr_engine.vision_client import ocr_document_text
from ocr_engine.pdf_render import render_pdf_pages_to_jpeg_bytes
from ocr_engine.lease_parser import extract_lease_fields

from ocr_engine.validators import find_required_fields, template_keyword_score
from ocr_engine.gms_llm import analyze_contract_text

from reco_engine.schemas import (
    RecoRankExplainRequest,
    RecoRankExplainResponse,
    CandidateRankExplain,
    PropertyBrief,
)
from reco_engine.ranker import calc_breakdown, calc_score_0_100, judge_code
from reco_engine.reco_llm import explain_rank_and_summary

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

@app.post("/reco/rank-explain", response_model=RecoRankExplainResponse)
async def reco_rank_explain(req: RecoRankExplainRequest):
    base = req.base
    cands = req.candidates or []

    if not cands:
        return {"status": "ok", "model": None, "results": []}

    # 1) 정량 점수 계산
    enriched = []
    for c in cands:
        bd = calc_breakdown(base, c)
        score = calc_score_0_100(bd)
        jc = judge_code(score)

        enriched.append({
            "propertyId": c.propertyId,
            "score": score,
            "judgeCode": jc,
            "breakdown": bd,
            "aptName": c.aptName,
            "rating": c.rating,
            "trend": c.trend,
            "price": c.price,
            "deposit": c.deposit,
            "area": c.area,
            "distM": c.distM,
        })

    # 2) topK만 LLM 설명 생성(비용 절약)
    enriched_sorted = sorted(enriched, key=lambda x: x["score"], reverse=True)[: req.topK]

    # LLM 입력 payload(설명에 필요한 것만)
    payload = {
        "base": base.model_dump(),
        "candidates": enriched_sorted,
        "maxReasons": req.maxReasons,
        "mode": req.mode,
    }

    llm_out = await explain_rank_and_summary(payload)

    # 3) LLM 비활성/실패 시: 기본 템플릿 설명으로 fallback
    if not llm_out.get("enabled"):
        results = []
        for item in enriched_sorted:
            pid = item["propertyId"]
            results.append({
                "propertyId": pid,
                "score": item["score"],
                "judgeCode": item["judgeCode"],
                "summary": "기준 매물과 조건이 비교적 유사해 보일 수 있어요.",
                "reasons": [
                    f"거리/가격/면적/평점/추세를 종합한 점수가 {item['score']}점이에요.",
                    f"평점은 {item.get('rating')}점, 거래 추세는 {item.get('trend')}로 분석됐어요.",
                ][: req.maxReasons],
                "breakdown": item["breakdown"],
            })
        return {"status": "ok", "model": None, "results": results, "error": llm_out.get("error")}

        # 4) LLM 결과 매핑 (propertyId 기준으로 합치기)
    llm_results = llm_out.get("results") or []
    llm_map = {
        int(x.get("propertyId")): x
        for x in llm_results
        if str(x.get("propertyId", "")).isdigit()
    }

    final = []
    for item in enriched_sorted:
        pid = item["propertyId"]
        lr = llm_map.get(pid, {})

        # LLM 키 이름(aiSummary/aiReasons/aiJudgeCode/aiScore)로 읽기
        summary = str(lr.get("aiSummary") or "").strip()
        reasons = lr.get("aiReasons") or []
        reasons = [str(x).strip() for x in reasons if str(x).strip()]

        # judgeCode / score도 LLM이 덮어쓰게 할지 선택 가능
        jc = str(lr.get("aiJudgeCode") or item["judgeCode"]).strip() or item["judgeCode"]
        ai_score = lr.get("aiScore")
        try:
            ai_score = float(ai_score) if ai_score is not None else None
        except:
            ai_score = None

        if not summary:
            summary = "두집이가 보기엔, 기준 매물과 조건이 꽤 비슷한 편이라 한 번 같이 비교해볼 만해요."

        # reasons가 너무 짧으면 정량정보 기반으로 보강
        if len(reasons) < 4:
            reasons = reasons + [
                f"거리·가격·면적·후기·거래흐름을 합쳐서 {item['score']}점으로 나왔어요.",
                f"후기 평점은 {item.get('rating')}점, 최근 거래 흐름은 {item.get('trend')}로 보여요.",
                "조건이 비슷해도 세대/층/단지 분위기에 따라 체감이 달라질 수 있으니 현장도 같이 확인해보면 좋아요.",
            ]
        reasons = reasons[: req.maxReasons]  # req.maxReasons가 3이면 3개로 잘림 (원하면 5로 올려)

        final.append({
            "propertyId": pid,
            "score": ai_score if ai_score is not None else item["score"],  # LLM 점수 쓰고 싶으면
            "judgeCode": jc,
            "summary": summary,
            "reasons": reasons,
            "breakdown": item["breakdown"],
        })

    return {
        "status": "ok",
        "model": llm_out.get("prompt_version"),
        "results": final,
        "error": None,
    }