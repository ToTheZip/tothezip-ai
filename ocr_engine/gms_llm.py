import os, json
import httpx
from typing import Dict, Any

GMS_BASE_URL = os.getenv("GMS_BASE_URL", "https://gms.ssafy.io/gmsapi/api.openai.com/v1")
GMS_KEY = os.getenv("GMS_KEY")

async def analyze_contract_text(full_text: str) -> Dict[str, Any]:
    if not GMS_KEY:
        return {"enabled": False, "error": "GMS_KEY not set"}

    prompt = (
        "다음은 OCR로 추출한 한국 임대차 계약서 텍스트입니다.\n"
        "법적 판단(진위 확정)은 하지 말고, 일반적인 계약서와 비교했을 때\n"
        "필수 항목 누락/빈칸, 문맥 단절, 비정상적 표현, 위조 의심 신호가 있는지 점검하세요.\n"
        "JSON으로만 답하세요. 스키마:\n"
        "{ \"suspicious\": boolean, \"risk\": 0-100, \"reasons\": string[] }\n\n"
        f"OCR TEXT:\n{full_text[:12000]}"  # 길이 제한(비용/토큰)
    )

    url = f"{GMS_BASE_URL}/responses"
    headers = {
        "Authorization": f"Bearer {GMS_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "gpt-4.1",
        "input": prompt,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()

    # responses API는 output 텍스트를 파싱해야 함(형태가 다양할 수 있음)
    # 여기서는 가장 단순한 케이스로 output_text 추출 시도
    text = data.get("output_text")
    if not text:
        # fallback: output 배열에서 text 모으기(최소 대응)
        out = []
        for item in data.get("output", []):
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    out.append(c.get("text", ""))
        text = "\n".join(out).strip()

    try:
        parsed = json.loads(text)
        return {"enabled": True, **parsed}
    except Exception:
        return {"enabled": True, "raw": text}
