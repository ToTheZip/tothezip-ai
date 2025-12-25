# reco_engine/reco_llm.py
import os, json
import httpx
from typing import Dict, Any
from reco_engine.reco_prompt import build_reco_prompt, PROMPT_VERSION

GMS_BASE_URL = os.getenv("GMS_BASE_URL", "https://gms.ssafy.io/gmsapi/api.openai.com/v1")
GMS_KEY = os.getenv("GMS_KEY")
GMS_MODEL = os.getenv("GMS_MODEL", "gpt-4.1")

def _extract_output_text(data: Dict[str, Any]) -> str:
    text = data.get("output_text")
    if text:
        return text.strip()

    out = []
    for item in data.get("output", []):
        for c in item.get("content", []):
            if c.get("type") == "output_text":
                out.append(c.get("text", ""))
    return "\n".join(out).strip()

def _safe_float(x, default=None):
    try:
        return float(x)
    except Exception:
        return default

async def explain_rank_and_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not GMS_KEY:
        return {"enabled": False, "error": "GMS_KEY not set"}

    prompt = build_reco_prompt(payload)

    url = f"{GMS_BASE_URL}/responses"
    headers = {
        "Authorization": f"Bearer {GMS_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": GMS_MODEL,
        "input": prompt,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()

    text = _extract_output_text(data)

    try:
        parsed = json.loads(text)
    except Exception:
        return {"enabled": True, "raw": text, "prompt_version": PROMPT_VERSION}

    results = parsed.get("results")
    if not isinstance(results, list):
        return {"enabled": True, "raw": text, "prompt_version": PROMPT_VERSION, "warning": "Invalid schema"}

    # 최소 보정/정규화
    normalized = []
    for item in results:
        pid = item.get("propertyId")
        if pid is None:
            continue

        aiScore = _safe_float(item.get("aiScore"), 0.0)
        code = str(item.get("aiJudgeCode", "RECO")).strip() or "RECO"

        summary = str(item.get("aiSummary", "")).strip()
        reasons = item.get("aiReasons") or []
        warnings = item.get("aiWarnings") or []

        reasons = [str(x).strip() for x in reasons if str(x).strip()]
        warnings = [str(x).strip() for x in warnings if str(x).strip()]

        breakdown = item.get("aiBreakdown") or {}
        # breakdown은 dict면 그대로 둠(없어도 OK)

        normalized.append({
            "propertyId": int(pid),
            "aiScore": aiScore,
            "aiJudgeCode": code,
            "aiSummary": summary,
            "aiReasons": reasons[:6],
            "aiWarnings": warnings[:2],
            "aiBreakdown": breakdown,
        })

    return {
        "enabled": True,
        "prompt_version": PROMPT_VERSION,
        "model": GMS_MODEL,
        "model_name": parsed.get("model_name", "reco-rank-explain-v3-dozip"),
        "results": normalized,
        "meta": parsed.get("meta", {}),
    }
