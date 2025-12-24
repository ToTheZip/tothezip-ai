import re
from typing import Dict, Any, List, Tuple

BLANK_PAT = re.compile(r"^(\s*|[_\-·•\.\(\)\[\]□■▢▣]+)$")

def _has_blank(value: str) -> bool:
    if value is None:
        return True
    v = value.strip()
    if v == "":
        return True
    # '____', '----', '()' 등 빈칸 기호
    if BLANK_PAT.match(v):
        return True
    # '미기재', '없음' 같은 표현도 빈칸 취급하고 싶으면 여기에 추가
    return False

def find_required_fields(full_text: str) -> Dict[str, Any]:
    """
    full_text에서 필수 항목이 '있는데 값이 비어있다' / '아예 없다'를 탐지.
    """
    text = full_text or ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # 계약서마다 표현이 조금씩 달라서 label 후보를 여러 개 둠
    required: List[Tuple[str, List[str]]] = [
        ("임대인",  [r"임\s*대\s*인", r"임대인"]),
        ("임차인",  [r"임\s*차\s*인", r"임차인"]),
        ("소재지",  [r"소\s*재\s*지", r"주소", r"소재지"]),
        ("보증금",  [r"보\s*증\s*금", r"전\s*세\s*금", r"임\s*대\s*보\s*증\s*금"]),
        ("차임",    [r"차\s*임", r"월\s*세", r"임\s*대\s*료"]),
        ("계약기간",[r"계\s*약\s*기\s*간", r"임\s*대\s*기\s*간"]),
        ("특약",    [r"특\s*약", r"특약사항"]),
        ("서명",    [r"서\s*명", r"날\s*인", r"인\s*감", r"서명\s*또는\s*날인"]),
    ]

    missing_fields: List[str] = []
    present_but_blank: List[str] = []

    # “라벨: 값” 패턴을 우선 탐지 (한 줄에 같이 있는 경우)
    for field_name, label_patterns in required:
        found_any = False
        blank = True

        for lp in label_patterns:
            # 라벨이 포함된 라인 찾기
            for line in lines:
                if re.search(lp, line):
                    found_any = True
                    # 라벨 뒤쪽 값을 분리 시도 (콜론/공백 뒤)
                    parts = re.split(lp, line, maxsplit=1)
                    tail = parts[1] if len(parts) == 2 else ""
                    tail = tail.lstrip(":： ").strip()

                    # tail이 비어있으면 다음 라인 값일 수도 있으니 다음 라인도 확인
                    if _has_blank(tail):
                        # 다음 라인에 값이 적히는 형태 탐지(간단)
                        # 실제로는 인덱스 기반으로 더 정교하게 가능
                        blank = True
                    else:
                        blank = False
                    break
            if found_any and not blank:
                break

        if not found_any:
            missing_fields.append(field_name)
        elif blank:
            present_but_blank.append(field_name)

    return {
        "missing_fields": missing_fields,
        "present_but_blank": present_but_blank,
    }

def template_keyword_score(full_text: str) -> Dict[str, Any]:
    """
    '일반적인 임대차 계약서'에서 자주 보이는 키워드/섹션 존재 여부로 점수화.
    """
    text = (full_text or "")
    keywords = [
        "주택임대차", "임대인", "임차인", "소재지", "보증금",
        "월세", "전세", "계약기간", "특약", "중개", "공인중개사",
        "작성일", "서명", "날인"
    ]
    found = [k for k in keywords if k in text]
    missing = [k for k in keywords if k not in text]
    score = len(found)

    return {"score": score, "found": found, "missing": missing}
