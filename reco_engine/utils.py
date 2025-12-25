import re
from typing import Optional, Any

def to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)

    s = str(v).strip()
    if not s:
        return None

    # "17,700", "43,000만", "  43000 " 같은 케이스 처리
    s = s.replace(",", "")
    nums = re.findall(r"[-]?\d+(\.\d+)?", s)
    if not nums:
        return None
    try:
        return float(nums[0])
    except:
        return None

def clamp01(x: Optional[float]) -> float:
    if x is None:
        return 0.0
    return max(0.0, min(1.0, x))
