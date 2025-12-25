import re
from typing import Optional, Dict
from reco_engine.schemas import PropertyBrief


def _to_num(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    only = re.sub(r"[^0-9.]", "", str(s).replace(",", ""))
    if not only:
        return None
    try:
        return float(only)
    except:
        return None


def _sim(a: Optional[float], b: Optional[float]) -> float:
    if a is None or b is None:
        return 0.0
    denom = max(abs(a), 1.0)
    diff = abs(a - b) / denom
    return max(0.0, 1.0 - diff)


def _trend_score(base_trend: Optional[str], cand_trend: Optional[str]) -> float:
    if not base_trend or not cand_trend:
        return 0.3
    if base_trend == "UNKNOWN" or cand_trend == "UNKNOWN":
        return 0.3
    if base_trend == cand_trend:
        return 1.0
    if "FLAT" in (base_trend, cand_trend):
        return 0.6
    return 0.2


def _is_monthly(p: PropertyBrief) -> bool:
    # dealType 필드 우선
    if p.dealType == "월세":
        return True
    # 혹시 extra에 type 넣어두는 케이스 대비
    if isinstance(p.extra, dict) and p.extra.get("type") == "월세":
        return True
    return False


def judge_code(score_0_100: float) -> str:
    if score_0_100 >= 85:
        return "STRONG_RECO"
    if score_0_100 >= 70:
        return "RECO"
    if score_0_100 >= 55:
        return "CAUTION"
    return "WEAK_RECO"


def calc_breakdown(base: PropertyBrief, c: PropertyBrief) -> Dict[str, float]:
    dist = c.distM if c.distM is not None else 99999.0
    dist_score = 1.0 / (1.0 + dist / 500.0)

    area_score = _sim(base.area, c.area)

    # price
    if _is_monthly(base):
        rent_score = _sim(_to_num(base.price), _to_num(c.price))
        dep_score = _sim(_to_num(base.deposit), _to_num(c.deposit))
        price_score = 0.6 * rent_score + 0.4 * dep_score
    else:
        price_score = _sim(_to_num(base.price), _to_num(c.price))

    rating_score = _sim(base.rating, c.rating)
    trend_score = _trend_score(base.trend, c.trend)

    return {
        "dist": float(dist_score),
        "price": float(price_score),
        "area": float(area_score),
        "rating": float(rating_score),
        "trend": float(trend_score),
    }


def calc_score_0_100(breakdown: Dict[str, float]) -> float:
    w = {"dist": 0.30, "price": 0.30, "area": 0.15, "rating": 0.15, "trend": 0.10}
    s = 0.0
    for k, wk in w.items():
        s += wk * float(breakdown.get(k, 0.0))
    return round(s * 100.0, 2)
