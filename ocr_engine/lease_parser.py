import re
from typing import Dict, Any, Optional

def _clean(text: str) -> str:
    return re.sub(r"[ \t]+", " ", (text or "")).strip()

def _line_after_label(full_text: str, label_regex: str) -> Optional[str]:
    for line in full_text.splitlines():
        if re.search(label_regex, line):
            parts = re.split(label_regex, line, maxsplit=1)
            if len(parts) == 2:
                return _clean(parts[1].lstrip(":： ").strip())
    return None

def extract_lease_fields(full_text: str) -> Dict[str, Any]:
    full_text = full_text or ""
    lines = [l.strip() for l in full_text.splitlines() if l.strip()]

    out: Dict[str, Any] = {
        "tenant_name": None,
        "address_raw": None,
        "debug": {"tenant_candidates": [], "address_candidates": []},
    }

    # -------------------------
    # 1) 주소 (지금 너 결과처럼 잘 나오게 유지)
    # -------------------------
    addr = _line_after_label(full_text, r"^\s*소\s*재\s*지\s*")
    if addr:
        addr = re.split(r"(토지|건물|구조|용도|대지권|면적)\b", addr)[0].strip()
        out["debug"]["address_candidates"].append(addr)
        out["address_raw"] = addr

    # -------------------------
    # 2) 임차인 이름: "임대인 임차인" 구역 근처에서 탐색
    # -------------------------
    # (A) '임대인 임차인' 라인 이후 30줄 안에서 '성명 김xx' 후보 수집
    start_idx = None
    for i, line in enumerate(lines):
        if "임대인" in line and "임차인" in line:
            start_idx = i
            break

    name_pat = re.compile(r"^성명\s*([가-힣]{2,4})$")
    # "B 성명 빈지향" 같은 변형도 허용
    name_pat2 = re.compile(r".*성명\s*([가-힣]{2,4})")

    if start_idx is not None:
        window = lines[start_idx : min(len(lines), start_idx + 30)]
        for w in window:
            m = name_pat.search(w) or name_pat2.search(w)
            if m:
                out["debug"]["tenant_candidates"].append(m.group(1))

        # 이 문서에서는 '임대인 이름'이 먼저 나오고 '임차인 이름'이 뒤에 나오는 경우가 많아서
        # 후보가 2개 이상이면 마지막 후보를 임차인으로 보는 게 실전에서 잘 맞음
        if len(out["debug"]["tenant_candidates"]) >= 2:
            out["tenant_name"] = out["debug"]["tenant_candidates"][-1]
        elif len(out["debug"]["tenant_candidates"]) == 1:
            # 후보가 1개면 그걸 사용 (문서 형식에 따라)
            out["tenant_name"] = out["debug"]["tenant_candidates"][0]

    # (B) fallback: 문서 끝부분에서 '성명 김xx'를 찾으면 마지막 것을 임차인 후보로
    if out["tenant_name"] is None:
        all_names = []
        for line in lines:
            m = name_pat.search(line) or name_pat2.search(line)
            if m:
                all_names.append(m.group(1))
        if all_names:
            out["debug"]["tenant_candidates"].extend(all_names)
            out["tenant_name"] = all_names[-1]

    # 오탐 제거
    blacklist = {"쌍방은", "임차인", "임대인", "성명", "주소"}
    if out["tenant_name"] in blacklist:
        out["tenant_name"] = None

    return out
