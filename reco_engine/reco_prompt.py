# reco_engine/reco_prompt.py
import json
from typing import Dict, Any

PROMPT_VERSION = "reco-rank-explain-v3-dozip"

def build_reco_prompt(payload: Dict[str, Any]) -> str:
    """
    payload = {
      "base": {...},
      "candidates": [...],
      "top_k": 10,
      "max_reasons": 4,
      ...
    }
    """

    schema = {
        "model_name": "string",
        "results": [
            {
                "propertyId": "int",
                "aiScore": "number (0~100)",
                "aiJudgeCode": "string (STRONG_RECO|RECO|CAUTION|WEAK)",
                "aiSummary": "string (2~3문장, 두집이 말투, 친절/자연스러움)",
                "aiReasons": [
                    "string (사용자 혜택/리스크 관점, 4~6개)",
                ],
                "aiWarnings": [
                    "string (주의/리스크 0~2개, 없으면 빈 배열)"
                ],
                "aiBreakdown": {
                    "dist": "number(0~1)",
                    "price": "number(0~1)",
                    "area": "number(0~1)",
                    "rating": "number(0~1)",
                    "trend": "number(0~1)"
                }
            }
        ],
        "meta": {
            "tone": "dozip-friendly",
            "notes": "string"
        }
    }

    rules = [
        "너는 ToTheZip 서비스의 안내자 '두집이'야. (캐릭터 느낌은 있지만 너무 동물처럼 말하지 마.)",
        "사용자에게 설명하듯 친절하고 자연스럽게 말해. 존댓말 유지.",
        "과장/단정 금지. 데이터에 없는 사실은 만들지 마.",
        "반드시 JSON만 출력. 코드블록/설명문 금지.",
        "aiSummary는 2~3문장. '왜 이 매물이 괜찮은지 + 어떤 점은 주의해야 하는지'가 들어가면 좋아.",
        "aiReasons는 최소 4개, 최대 6개. '점수 이름 나열' 금지. 반드시 사용자 입장에서 의미 있는 표현으로 풀어써.",
        "가능하면 비교형 문장으로 작성(기준 매물 대비). 예: '가격이 더 낮은 편이라 부담이 덜할 수 있어요.'",
        "trend는 UP/DOWN/FLAT/UNKNOWN을 보고 의미를 풀어 설명해.",
        "rating이 None이면 '후기 데이터가 부족해요'처럼 말해.",
        "최근 거래 series가 있으면 '최근 n건 기준' 같은 표현을 써도 되지만, 숫자 조작은 하지 마."
    ]

    return (
        "출력 JSON 스키마(반드시 준수):\n"
        f"{json.dumps(schema, ensure_ascii=False)}\n\n"
        "작성 규칙:\n- " + "\n- ".join(rules) + "\n\n"
        "입력 데이터(JSON):\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
