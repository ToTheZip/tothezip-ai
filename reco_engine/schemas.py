from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class PricePoint(BaseModel):
    date: str
    amount: str


class PropertyBrief(BaseModel):
    propertyId: int
    aptName: Optional[str] = None
    dealType: Optional[str] = None  # 월세/전세/매매 (base.type도 여기에 넣을 수 있음)

    price: Optional[str] = None
    deposit: Optional[str] = None
    area: Optional[float] = None
    floor: Optional[int] = None
    buildYear: Optional[int] = None

    distM: Optional[float] = None

    # ✅ 추가
    rating: Optional[float] = None
    recentPriceSeries: Optional[List[PricePoint]] = None
    trend: Optional[str] = None  # UP/DOWN/FLAT/UNKNOWN

    extra: Optional[Dict[str, Any]] = None


class RecoRankExplainRequest(BaseModel):
    base: PropertyBrief
    candidates: List[PropertyBrief]
    mode: str = Field("compare", description="compare")
    topK: int = Field(10, ge=1, le=30)
    maxReasons: int = Field(3, ge=1, le=5)


class CandidateRankExplain(BaseModel):
    propertyId: int
    score: float
    judgeCode: str
    summary: str
    reasons: List[str]
    breakdown: Dict[str, float] = {}


class RecoRankExplainResponse(BaseModel):
    status: str = "ok"
    model: Optional[str] = None
    results: List[CandidateRankExplain]
    error: Optional[str] = None
