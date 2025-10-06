from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List

class MetricsSummary(BaseModel):
    n: int
    n_pos: int
    auprc: float
    brier: float
    ece: float
    recall_small_at_1pct: Optional[float] = None
    source: str = Field(description="Path used to compute metrics")

class BenchmarkRow(BaseModel):
    id: str
    name: str
    auprc: Optional[float] = None
    brier: Optional[float] = None
    recall_small_at_1pct: Optional[float] = None

class BenchmarkReport(BaseModel):
    rows: List[BenchmarkRow]
    table_path: str

class Candidate(BaseModel):
    star: str
    label: Optional[int] = None
    p_final: float
    extra: dict = Field(default_factory=dict)

class CandidatePage(BaseModel):
    total: int
    items: List[Candidate]
